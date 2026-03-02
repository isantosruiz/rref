# RREF Web App (Python + Vercel)

Aplicacion web en Python para reducir matrices aumentadas a forma escalonada reducida por renglones (RREF), mostrando cada operacion elemental y la matriz resultante en cada paso con LaTeX.

## Funcionalidades

- Entrada de matriz aumentada.
- Entrada de sistema de ecuaciones lineales en forma simbolica.
- Inferencia automatica de variables (o definicion manual).
- Reduccion RREF paso a paso con:
  - operacion elemental sobre renglones,
  - nueva matriz tras cada operacion,
  - render de LaTeX via MathJax.

## Estructura

- `api/index.py`: app Flask + logica de parseo y RREF.
- `api/templates/index.html`: interfaz de usuario.
- `api/static/styles.css`: estilos.
- `vercel.json`: configuracion de despliegue en Vercel.

## Ejecutar localmente

1. Crear entorno virtual e instalar dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Ejecutar la app:

```bash
flask --app api/index.py run --debug
```

3. Abrir:

`http://127.0.0.1:5000`

## Despliegue en Vercel

1. Instala la CLI de Vercel si no la tienes:

```bash
npm i -g vercel
```

2. Desde la raiz del proyecto, despliega:

```bash
vercel
```

3. Para produccion:

```bash
vercel --prod
```
