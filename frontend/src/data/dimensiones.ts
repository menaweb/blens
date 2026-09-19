/**
 * Copia de las cinco preguntas de la categorización.
 *
 * Los textos son los del handoff de diseño y son definitivos: el vocabulario del ENS es
 * parte del producto. El orden también es el suyo (no el de ACIDA), porque va de lo más
 * intuitivo a lo más abstracto.
 */
export type Nivel = 'NA' | 'BAJO' | 'MEDIO' | 'ALTO'

export interface OpcionDimension {
  nivel: Nivel
  etiqueta: string
  ejemplo: string
}

export interface PreguntaDimension {
  dim: 'C' | 'I' | 'T' | 'A' | 'D'
  nombre: string
  corto: string
  pregunta: string
  ayuda: string
  opciones: OpcionDimension[]
}

const NIVELES: Nivel[] = ['NA', 'BAJO', 'MEDIO', 'ALTO']
const ETIQUETAS = ['No aplica', 'Bajo', 'Medio', 'Alto']

function opciones(ejemplos: string[]): OpcionDimension[] {
  return ejemplos.map((ejemplo, i) => ({ nivel: NIVELES[i], etiqueta: ETIQUETAS[i], ejemplo }))
}

export const DIMENSIONES: PreguntaDimension[] = [
  {
    dim: 'C',
    nombre: 'Confidencialidad',
    corto: 'Confid.',
    pregunta: '¿Qué pasaría si alguien de fuera viera la información de este servicio?',
    ayuda: 'Piensa en quién no debería verla: datos de vecinos, expedientes, nóminas, historiales.',
    opciones: opciones([
      'El servicio solo maneja información ya pública, como un tablón de anuncios.',
      'Sería incómodo pero se resolvería: un listado interno sin datos personales.',
      'Habría perjuicio serio: datos personales de vecinos, expedientes en tramitación.',
      'Sería muy grave: datos de salud, antecedentes, información de seguridad ciudadana.',
    ]),
  },
  {
    dim: 'I',
    nombre: 'Integridad',
    corto: 'Integr.',
    pregunta: '¿Qué pasaría si alguien alterara los datos sin que os dierais cuenta?',
    ayuda: 'Un importe cambiado, una fecha de registro movida, un documento sustituido.',
    opciones: opciones([
      'Los datos se regeneran solos desde otra fuente y no hay decisión que dependa de ellos.',
      'Se detectaría pronto y se corregiría sin consecuencias fuera de la casa.',
      'Afectaría a decisiones o derechos: padrón, registro de entrada, subvenciones.',
      'Podría invalidar actos administrativos o poner en riesgo a personas.',
    ]),
  },
  {
    dim: 'D',
    nombre: 'Disponibilidad',
    corto: 'Disp.',
    pregunta: '¿Cuánto tiempo puede estar caído el servicio sin que sea un problema serio?',
    ayuda: 'Cuenta desde que deja de funcionar hasta que alguien de fuera lo nota y protesta.',
    opciones: opciones([
      'No hay servicio en línea: si se cae, se trabaja igual en papel o por teléfono.',
      'Varios días. Se puede avisar y reanudar sin más.',
      'Unas horas. Hay plazos administrativos o atención al público que se resienten.',
      'Minutos. Es un servicio crítico o de emergencias.',
    ]),
  },
  {
    dim: 'A',
    nombre: 'Autenticidad',
    corto: 'Autent.',
    pregunta: '¿Qué pasaría si alguien se hiciera pasar por otra persona en este servicio?',
    ayuda: 'Presentar una instancia en nombre de un vecino, firmar como un funcionario que no es.',
    opciones: opciones([
      'No hay identificación: cualquiera puede usarlo de forma anónima y no pasa nada.',
      'Se notaría y se anularía la operación sin perjuicio real.',
      'Se podrían presentar trámites o acceder a expedientes en nombre de otro.',
      'Se podrían firmar resoluciones o mover fondos suplantando a un cargo.',
    ]),
  },
  {
    dim: 'T',
    nombre: 'Trazabilidad',
    corto: 'Trazab.',
    pregunta: '¿Necesitáis poder demostrar quién hizo cada cosa y cuándo?',
    ayuda: 'Ante una reclamación, una inspección o una denuncia, qué tendríais que poder enseñar.',
    opciones: opciones([
      'No hay actuaciones que haya que atribuir a nadie.',
      'Basta con saber, a grandes rasgos, qué pasó.',
      'Hay que poder reconstruir quién accedió o modificó qué, con fecha.',
      'Se exige registro completo y conservado, con valor probatorio.',
    ]),
  },
]
