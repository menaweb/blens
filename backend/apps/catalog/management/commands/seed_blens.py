"""Carga la capa propia del catálogo: checks, preguntas y plantillas de evidencia.

Es el contenido que distingue a BLENS del texto de la norma (§3.1: el OSCAL oficial no
trae checks, ni evidencias esperadas, ni preguntas). Vive en `db/seed/blens/*.yaml`, cuelga
de la `CatalogVersion` vigente y se ancla siempre a ids OSCAL.

Idempotente: reescribe la capa entera del catálogo indicado, así que se puede repetir sin
miedo. **Hay que volver a ejecutarlo después de cada `import_ens_oscal`**, igual que
`seed_magerit`, porque todo cuelga de las medidas.

Valida antes de escribir y no escribe nada si algo falla: una medida que ya no existe, una
plantilla citada por un check que no está, una preferencia repetida dentro de un grupo o un
hecho que nadie emite detienen la carga entera con el detalle. Es la misma batería que
`db/seed/blens/validate_seed.py` pasa en CI, aquí contra la base de datos.
"""

from __future__ import annotations

import collections
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import (
    CatalogVersion,
    EnsCheck,
    EnsMeasure,
    EnsRefuerzo,
    EnsRequirementItem,
    EvidenceTemplate,
    MetodoVerificacion,
    ProductEvidenceHint,
    ProfileBlock,
    ProfileOption,
    ProfileQuestion,
    TipoEvidencia,
    TipoPregunta,
)
from engines.evidence_engine import (
    bloques_desde,
    plantillas_desde,
    pregunta_desde,
    preguntas_desde,
)
from engines.evidence_engine.jsonlogic import ReglaInvalida, hechos_citados

RAIZ = Path(__file__).resolve().parents[5]
SEED = RAIZ / "db" / "seed" / "blens"


def _documentos(patron: str) -> list[tuple[str, dict]]:
    ficheros = sorted(SEED.glob(patron))
    if not ficheros:
        raise CommandError(f"No hay ficheros del seed que casen con {patron} en {SEED}")
    return [(f.name, yaml.safe_load(f.read_text(encoding="utf-8"))) for f in ficheros]


class Command(BaseCommand):
    help = "Carga checks, preguntas de perfilado y plantillas de evidencia (capa propia)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--catalog", help="Código de la CatalogVersion; por defecto, la vigente."
        )
        parser.add_argument(
            "--layer-version",
            default="",
            help="Versión de la capa propia que se anota en la CatalogVersion.",
        )

    def handle(self, *args, **opciones) -> None:
        version = (
            CatalogVersion.objects.filter(code=opciones["catalog"]).first()
            if opciones["catalog"]
            else CatalogVersion.current()
        )
        if version is None:
            raise CommandError(
                "No hay ninguna versión del catálogo vigente. Ejecuta antes import_ens_oscal."
            )

        preguntas = _documentos("questions.*.yaml")
        plantillas = _documentos("evidence_templates.*.yaml")
        checks = _documentos("checks/checks.*.yaml")

        medidas = {m.code: m for m in EnsMeasure.objects.filter(catalog=version)}
        refuerzos = {r.code: r for r in EnsRefuerzo.objects.filter(measure__catalog=version)}
        items = self._indice_de_items(version)

        self._validar(preguntas, plantillas, checks, medidas, refuerzos, items)

        with transaction.atomic():
            self._borrar_capa(version)
            n_bloques, n_preguntas, n_opciones = self._cargar_preguntas(version, preguntas)
            n_plantillas, n_pistas = self._cargar_plantillas(
                version, plantillas, medidas, refuerzos
            )
            n_checks = self._cargar_checks(version, checks, medidas, refuerzos, items)
            if opciones["layer_version"]:
                CatalogVersion.objects.filter(pk=version.pk).update(
                    blens_layer_version=opciones["layer_version"]
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Capa propia cargada en {version.code}: {n_bloques} bloques, "
                f"{n_preguntas} preguntas ({n_opciones} opciones), "
                f"{n_plantillas} plantillas de evidencia ({n_pistas} pistas por producto) "
                f"y {n_checks} checks."
            )
        )

    # --- validación --------------------------------------------------------------

    def _indice_de_items(self, version) -> dict[tuple[str, str, str], EnsRequirementItem]:
        """Los items por (medida, etiqueta, etiqueta del padre).

        Las etiquetas **no son únicas** entre medidas (§6) y las de los subapartados son
        literalmente «a)», «b)». Por eso la clave lleva la medida y, cuando hace falta, el
        padre: es la que usan los checks del seed.
        """
        indice = {}
        for item in EnsRequirementItem.objects.filter(catalog=version).select_related(
            "measure", "parent"
        ):
            padre = item.parent.label if item.parent_id else ""
            indice[(item.measure.code, item.label, padre)] = item
        return indice

    def _validar(self, preguntas, plantillas, checks, medidas, refuerzos, items) -> None:
        errores: list[str] = []

        # Bloques: el mismo código tiene que contar lo mismo en todos los ficheros.
        titulos = collections.defaultdict(set)
        for _, doc in preguntas:
            for bloque in bloques_desde(doc):
                titulos[bloque["code"]].add(bloque["titulo"])
        for code, vistos in sorted(titulos.items()):
            if len(vistos) > 1:
                errores.append(f"el bloque {code} se llama de varias formas: {sorted(vistos)}")

        emitidos, usados, codigos_pregunta = set(), set(), set()
        for nombre, doc in preguntas:
            for pregunta in preguntas_desde(doc):
                if pregunta.code in codigos_pregunta:
                    errores.append(f"{nombre}: pregunta duplicada {pregunta.code}")
                codigos_pregunta.add(pregunta.code)
                if pregunta.tipo not in TipoPregunta.values:
                    errores.append(f"{pregunta.code}: tipo desconocido {pregunta.tipo!r}")
                for opcion in pregunta.opciones:
                    emitidos |= set(opcion.emits)
                emitidos |= {campo.code for campo in pregunta.campos} | set(pregunta.emits)
                usados |= self._hechos(pregunta.show_if, pregunta.code, errores)

        codigos_plantilla = set()
        grupos = collections.defaultdict(list)
        for nombre, doc in plantillas:
            for plantilla in plantillas_desde(doc):
                if plantilla.code in codigos_plantilla:
                    errores.append(f"{nombre}: plantilla duplicada {plantilla.code}")
                codigos_plantilla.add(plantilla.code)
                if plantilla.measure not in medidas:
                    errores.append(f"{plantilla.code}: la medida {plantilla.measure} no existe")
                if plantilla.refuerzo and plantilla.refuerzo not in refuerzos:
                    errores.append(f"{plantilla.code}: el refuerzo {plantilla.refuerzo} no existe")
                if plantilla.tipo not in TipoEvidencia.values:
                    errores.append(f"{plantilla.code}: tipo desconocido {plantilla.tipo!r}")
                if plantilla.option_group:
                    grupos[plantilla.option_group].append(plantilla.preferencia)
                usados |= self._hechos(plantilla.applies_if, plantilla.code, errores)

        for grupo, preferencias in sorted(grupos.items()):
            if len(preferencias) != len(set(preferencias)):
                errores.append(f"el grupo {grupo} repite preferencia: {sorted(preferencias)}")

        for hecho in sorted(usados - emitidos):
            errores.append(f"hecho usado en una regla y que nadie emite: {hecho}")

        codigos_check = set()
        for nombre, doc in checks:
            for check in doc["checks"]:
                if check["code"] in codigos_check:
                    errores.append(f"{nombre}: check duplicado {check['code']}")
                codigos_check.add(check["code"])
                if check["measure"] not in medidas:
                    errores.append(f"{check['code']}: la medida {check['measure']} no existe")
                if check.get("refuerzo") and check["refuerzo"] not in refuerzos:
                    errores.append(f"{check['code']}: el refuerzo {check['refuerzo']} no existe")
                clave = (check["measure"], check["item"], check.get("item_padre", "") or "")
                if clave not in items:
                    errores.append(f"{check['code']}: no hay requisito {clave} en el catálogo")
                for metodo in check.get("metodo") or []:
                    if metodo not in MetodoVerificacion.values:
                        errores.append(f"{check['code']}: método desconocido {metodo!r}")
                for evidencia in check.get("evidencia_esperada") or []:
                    if evidencia not in codigos_plantilla:
                        errores.append(f"{check['code']}: la evidencia {evidencia} no existe")

        if errores:
            raise CommandError(
                "El seed de la capa propia no es válido:\n  - " + "\n  - ".join(errores)
            )

    def _hechos(self, regla, donde: str, errores: list[str]) -> set[str]:
        try:
            return hechos_citados(regla)
        except ReglaInvalida as error:  # pragma: no cover - solo si el seed trae basura
            errores.append(f"{donde}: regla no evaluable ({error})")
            return set()

    # --- carga ---------------------------------------------------------------------

    def _borrar_capa(self, version) -> None:
        """Se reescribe entera. Nada de tenant cuelga del catálogo: cuelga de sus copias."""
        EnsCheck.objects.filter(catalog=version).delete()
        ProductEvidenceHint.objects.filter(catalog=version).delete()
        EvidenceTemplate.objects.filter(catalog=version).delete()
        ProfileQuestion.objects.filter(catalog=version).delete()
        ProfileBlock.objects.filter(catalog=version).delete()

    def _cargar_preguntas(self, version, documentos) -> tuple[int, int, int]:
        bloques: dict[str, dict] = {}
        for _, doc in documentos:
            for bloque in bloques_desde(doc):
                bloques.setdefault(bloque["code"], {"titulo": bloque["titulo"], "minutos": 0})

        # Se recorre el YAML crudo, no solo el dataclass del motor: al motor le da igual
        # cómo esté redactada una pregunta, y al cliente no (§1bis del cuestionario).
        crudas = [datos for _, doc in documentos for datos in doc["questions"]]
        for datos in crudas:
            bloques[datos["bloque"]]["minutos"] += int(datos.get("minutos_estimados", 1))

        creados = {
            code: ProfileBlock.objects.create(
                catalog=version,
                code=code,
                titulo=datos["titulo"],
                # Lo que se le promete al cliente sale de sus preguntas, no de un número
                # escrito a mano en cada fichero de familia.
                minutos_estimados=datos["minutos"],
                orden=orden,
            )
            for orden, (code, datos) in enumerate(sorted(bloques.items()), start=1)
        }

        filas_opcion = []
        for datos in crudas:
            pregunta = pregunta_desde(datos)
            fila = ProfileQuestion.objects.create(
                catalog=version,
                code=pregunta.code,
                bloque=creados.get(pregunta.bloque),
                tipo=pregunta.tipo,
                texto=pregunta.texto,
                show_if=pregunta.show_if,
                campos=[{"code": c.code, "label": c.label} for c in pregunta.campos],
                emits=dict(pregunta.emits),
                funcion=pregunta.funcion,
                minutos_estimados=pregunta.minutos_estimados,
                orden=pregunta.orden,
                por_que=datos.get("por_que", ""),
                como_saberlo=datos.get("como_saberlo", ""),
                a_quien_preguntar=datos.get("a_quien_preguntar", ""),
                glosario=dict(datos.get("glosario") or {}),
                ejemplos=list(datos.get("ejemplos") or []),
            )
            filas_opcion += [
                ProfileOption(
                    question=fila,
                    code=opcion.code,
                    label=opcion.label,
                    emits=dict(opcion.emits),
                    orden=orden,
                )
                for orden, opcion in enumerate(pregunta.opciones, start=1)
            ]
        ProfileOption.objects.bulk_create(filas_opcion)
        return len(creados), len(crudas), len(filas_opcion)

    def _cargar_plantillas(self, version, documentos, medidas, refuerzos) -> tuple[int, int]:
        n_plantillas = n_pistas = 0
        for _, doc in documentos:
            for orden, datos in enumerate(doc["templates"], start=1):
                plantilla = plantillas_desde({"templates": [datos]})[0]
                fila = EvidenceTemplate.objects.create(
                    catalog=version,
                    code=plantilla.code,
                    measure=medidas[plantilla.measure],
                    refuerzo=refuerzos.get(plantilla.refuerzo) if plantilla.refuerzo else None,
                    titulo=plantilla.titulo,
                    instrucciones=datos.get("instrucciones", ""),
                    tipo=plantilla.tipo,
                    formatos=list(datos.get("formatos") or []),
                    option_group=plantilla.option_group,
                    preferencia=plantilla.preferencia,
                    applies_if=plantilla.applies_if,
                    criterios_aceptacion=list(datos.get("criterios_aceptacion") or []),
                    rechazos_tipicos=list(datos.get("rechazos_tipicos") or []),
                    obligatoria=plantilla.obligatoria,
                    vigencia_dias=plantilla.vigencia_dias,
                    carpeta_paquete=plantilla.carpeta_paquete,
                    generable=plantilla.generable,
                    ejemplo_url=datos.get("ejemplo_url", ""),
                    orden=orden,
                )
                n_plantillas += 1
                for pista in datos.get("product_hints") or []:
                    ProductEvidenceHint.objects.create(
                        catalog=version,
                        template=fila,
                        producto_match=dict(pista.get("match") or {}),
                        instrucciones=pista.get("instrucciones", ""),
                    )
                    n_pistas += 1
        return n_plantillas, n_pistas

    def _cargar_checks(self, version, documentos, medidas, refuerzos, items) -> int:
        plantillas = {t.code: t for t in EvidenceTemplate.objects.filter(catalog=version)}
        total = 0
        for _, doc in documentos:
            for orden, datos in enumerate(doc["checks"], start=1):
                clave = (datos["measure"], datos["item"], datos.get("item_padre", "") or "")
                check = EnsCheck.objects.create(
                    catalog=version,
                    code=datos["code"],
                    measure=medidas[datos["measure"]],
                    refuerzo=(
                        refuerzos.get(datos.get("refuerzo")) if datos.get("refuerzo") else None
                    ),
                    item=items[clave],
                    descripcion=datos["descripcion"],
                    metodo=list(datos.get("metodo") or []),
                    orden=orden,
                )
                esperadas = [plantillas[c] for c in datos.get("evidencia_esperada") or []]
                if esperadas:
                    check.evidencia_esperada.set(esperadas)
                total += 1
        return total
