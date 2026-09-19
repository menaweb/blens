<script setup lang="ts">
/**
 * P16 · Crear cuenta desde el resultado de la categorización.
 *
 * No es un formulario que aparece de la nada: arriba va lo que la persona acaba de
 * obtener, para que vea qué está guardando. Si ese resultado caducó, el alta sigue
 * adelante y se dice sin culpar a nadie.
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { confirmarCorreo, crearCuenta, reenviarCodigo } from '@/api/auth'
import { ErrorApi, pedir } from '@/api/http'

const ruta = useRoute()
const router = useRouter()

const token = String(ruta.query.resultado ?? '')
const resultado = ref<{ categoria: string } | null>(null)
const resultadoCaducado = ref(false)

const organizacion = ref('')
const nombre = ref('')
const email = ref('')
const password = ref('')

const paso = ref<'datos' | 'confirmar'>('datos')
const codigo = ref('')
const error = ref('')
const aviso = ref('')
const enviando = ref(false)

onMounted(async () => {
  if (!token) return
  try {
    resultado.value = await pedir<{ categoria: string }>(`/api/categorization/report/${token}`)
  } catch {
    // 404 o caducado: no se bloquea nada, solo se avisa.
    resultadoCaducado.value = true
  }
})

async function registrar() {
  error.value = ''
  enviando.value = true
  try {
    const hecha = await crearCuenta({
      email: email.value,
      password: password.value,
      organizacion: organizacion.value,
      nombre: nombre.value,
      nombre_sistema: '',
      informe_token: token,
    })
    aviso.value = hecha.aviso
    paso.value = 'confirmar'
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido crear la cuenta.'
  } finally {
    enviando.value = false
  }
}

async function confirmar() {
  error.value = ''
  enviando.value = true
  try {
    await confirmarCorreo(email.value, codigo.value)
    router.push({ name: 'entrar', query: { correo: email.value } })
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido confirmar el correo.'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="alta">
    <div v-if="resultado" class="resultado">
      <p class="etiqueta">Vas a guardar tu categorización</p>
      <p class="categoria">Categoría {{ resultado.categoria }}</p>
      <p class="pie">Se convertirá en tu primer sistema, con sus cinco dimensiones.</p>
    </div>
    <p v-else-if="resultadoCaducado" class="caducado" role="status">
      Tu categorización ya no está disponible: los resultados sin cuenta caducan. Puedes crear
      la cuenta igualmente y repetirla después, son dos minutos.
    </p>

    <h1>{{ paso === 'datos' ? 'Crear cuenta' : 'Confirma tu correo' }}</h1>

    <form v-if="paso === 'datos'" @submit.prevent="registrar">
      <label>
        Organización
        <input v-model="organizacion" required minlength="2" autocomplete="organization" />
      </label>
      <label>
        Tu nombre
        <input v-model="nombre" autocomplete="name" />
      </label>
      <label>
        Correo
        <input v-model="email" type="email" required autocomplete="email" />
      </label>
      <label>
        Contraseña
        <input
          v-model="password"
          type="password"
          required
          minlength="12"
          autocomplete="new-password"
        />
        <small>Doce caracteres o más.</small>
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="enviando">
        {{ enviando ? 'Creando…' : 'Crear cuenta' }}
      </button>
    </form>

    <form v-else @submit.prevent="confirmar">
      <p>
        Te hemos enviado un código a <strong>{{ email }}</strong
        >. Escríbelo aquí para terminar.
      </p>
      <p v-if="aviso" class="caducado" role="status">{{ aviso }}</p>
      <label>
        Código
        <input v-model="codigo" required inputmode="numeric" autocomplete="one-time-code" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="enviando">Confirmar</button>
      <button type="button" class="secundario" @click="reenviarCodigo(email)">
        Reenviar el código
      </button>
    </form>
  </section>
</template>

<style scoped>
.alta {
  max-width: var(--col);
  margin: 0 auto;
  padding: 32px 16px;
}
.resultado {
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radio);
  padding: 16px;
  margin-bottom: 24px;
}
.etiqueta,
.pie {
  margin: 0;
  color: var(--ink-600);
  font-size: 0.9rem;
}
.categoria {
  margin: 4px 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--brand-900);
}
.caducado {
  background: var(--surface);
  border-left: 3px solid var(--nivel-medio-fg);
  padding: 12px 16px;
  color: var(--ink-600);
}
form {
  display: grid;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 24px;
}
label {
  display: grid;
  gap: 4px;
  font-weight: 500;
}
input {
  font: inherit;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radio);
}
small {
  color: var(--ink-600);
  font-weight: 400;
}
button {
  background: var(--brand-700);
  color: #fff;
  border: 0;
  border-radius: var(--radio);
  padding: 12px 16px;
  font-size: 1rem;
  cursor: pointer;
}
button.secundario {
  background: transparent;
  color: var(--brand-700);
}
.error {
  color: var(--nivel-alto-fg);
  margin: 0;
}
</style>
