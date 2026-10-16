# Repositorio de Presentaciones Académicas

Un hub estático para alojar, organizar y buscar presentaciones HTML en GitHub Pages. El índice se genera con Python y el sitio funciona sin servidor ni dependencias de frontend.

## Funciones

- Búsqueda de texto completo en títulos, etiquetas, descripciones y diapositivas.
- Filtros por curso y etiquetas; orden por fecha, título o curso.
- Portadas SVG generadas para las tarjetas del catálogo. También se pueden indicar imágenes propias.
- Favoritos, colecciones y presentaciones recientes guardados en el navegador.
- Enlace para continuar una presentación desde la última diapositiva abierta.
- Índice de diapositivas con enlaces directos (`?slide=4`), vista de texto, tarjetas de repaso y referencias.
- Guía imprimible desde cada presentación. El diálogo de impresión del navegador permite guardarla como PDF.
- Comprobaciones automáticas de índice y metadatos con GitHub Actions.

## Estructura

```text
.
├── index.html
├── presentaciones.json             # Generado por indexer.py
├── indexer.py
├── tests/
├── slides/
│   └── fecha-tema/
│       ├── index.html
│       └── catalog-preview.generated.svg
└── .github/workflows/
```

## Añadir una presentación

Guarda un archivo HTML dentro de su propia carpeta en `slides/`. Usa una fecha ISO y añade estos metadatos en `<head>`:

```html
<title>Título de la presentación</title>
<meta name="date" content="2026-10-03">
<meta name="course" content="Ingeniería en Sistemas de Información">
<meta name="tags" content="git, reproducibilidad, sistemas">
<meta name="description" content="Resumen breve para el catálogo.">
<meta name="author" content="Grupo 5">
<meta name="duration-minutes" content="12">
<meta name="preview" content="portada.png">
```

`title` usa el elemento `<title>` como alternativa. `author`, `duration-minutes` y `preview` son opcionales. Si no indicas una duración, el catálogo estima 1,2 minutos por diapositiva y marca el valor como aproximado. Si no indicas una portada, el indexador genera una SVG con el título y el curso. La ruta de `preview` debe ser relativa al archivo HTML.

El indexador cuenta las diapositivas marcadas con `class="slide"` y toma el primer encabezado de cada diapositiva para construir el índice. El texto de `<script>`, `<style>` y SVG no entra en la búsqueda.

## Generar y validar

Desde la raíz del repositorio, ejecuta:

```bash
python3 indexer.py
python3 -m unittest discover -s tests -v
```

Confirma `presentaciones.json` y las portadas SVG generadas junto con los cambios de cada presentación. GitHub Actions vuelve a generar el índice y falla si los archivos generados no están actualizados.

## Usar el hub y los decks

- Usa el filtro **Mi biblioteca** para ver todas las presentaciones, tus guardadas o una colección.
- Crea colecciones desde el catálogo. Los favoritos y colecciones viven en `localStorage` del navegador.
- En un deck, pulsa **ÍNDICE** o la tecla `o` para abrir el índice y las tarjetas de repaso.
- Copia el enlace de una diapositiva desde el panel. El enlace abre ese número directamente.
- Pulsa **Imprimir guía / PDF** para abrir una guía con el contenido de las diapositivas, preguntas y referencias.

Los datos de favoritos, colecciones y progreso son locales al navegador. El hub no requiere cuentas ni un backend.
