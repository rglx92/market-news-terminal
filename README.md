# Market News Terminal V2

Dashboard diario para depurar noticias bursátiles, atribuirlas a la empresa correcta y separar tres preguntas diferentes:

1. ¿La noticia es positiva o negativa para la empresa?
2. ¿Tiene impacto material sobre SPY?
3. ¿La reacción del mercado ofrece una entrada razonable o ya está descontada?

## Mejoras de V2

- Reasigna titulares al ticker realmente mencionado. Un artículo de Marvell encontrado en el feed de SPY se clasifica como `MRVL`, no como `SPY`.
- Elimina duplicados globalmente por URL y similitud del titular.
- Penaliza listas generales como “Top Midday Decliners” y artículos que mencionan muchas compañías.
- Añade un puntaje de **Relevancia** y conserva el ticker de origen para auditoría.
- Muestra el modo real usado en cada análisis: **AI** o **RULES**.
- Si OpenAI falla, conserva el análisis de respaldo y muestra el error dentro de **Diagnóstico de IA**.
- Combina SPY, QQQ, IWM, VIX, US10Y y DXY en un régimen macro risk-on/risk-off.
- La calibración no muestra una tasa de acierto como concluyente hasta tener al menos 20 observaciones.
- Incluye pruebas para atribución, deduplicación, ruido y régimen macro.

## Publicación existente en Streamlit

Para actualizar la app que ya publicaste, consulta [`UPDATE_GITHUB.md`](UPDATE_GITHUB.md). No necesitas volver a crear el repository ni volver a pegar tus Secrets.

## Secrets recomendados

```toml
FINNHUB_API_KEY = "TU_CLAVE_FINNHUB"
OPENAI_API_KEY = "TU_CLAVE_OPENAI"
OPENAI_MODEL = "gpt-5.6"
OPENAI_TIMEOUT_SECONDS = "45"
SEC_USER_AGENT = "MarketNewsTerminal/0.2 tu-correo@example.com"
APP_TIMEZONE = "America/Chicago"
DAILY_LOOKBACK_DAYS = "2"
DAILY_MAX_NEWS_PER_TICKER = "4"
DAILY_MIN_RELEVANCE = "60"
DAILY_MIN_TRADE_QUALITY = "35"
```

Las claves reales deben permanecer en Streamlit **Secrets**. No las guardes en GitHub.

## Interfaz

- **Radar:** impacto fundamental frente a calidad del trade.
- **Feed visual:** tarjetas con ticker primario, modo, relevancia, evidencia y riesgos.
- **SPY & macro:** sesgo combinado de noticias y régimen de mercado.
- **Historial y calibración:** predicciones guardadas y retornos posteriores.
- **Diagnóstico de IA:** aparece cuando alguna llamada a OpenAI falla.

## Instalación local

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Interpretación

- **Empresa (-100 a +100):** impacto fundamental estimado para el ticker primario.
- **SPY (-100 a +100):** impacto material estimado sobre el índice.
- **Relevancia (0 a 100):** fuerza de la atribución entre titular y ticker.
- **Confirmación (0 a 100):** coincidencia entre la señal y el movimiento observado.
- **Trade (0 a 100):** prioridad de revisión; no es una orden de compra o venta.

## Validación realizada

- Compilación de todos los archivos Python.
- Ocho pruebas unitarias aprobadas.
- Prueba de arranque de Streamlit y render inicial sin excepciones.

## Limitaciones

El sistema no puede predecir el mercado con certeza. Los feeds gratuitos pueden contener retrasos o titulares incompletos. La base SQLite de Streamlit Community Cloud no es almacenamiento permanente y puede perderse después de reconstrucciones de la app.

Herramienta educativa y de investigación; no constituye asesoría financiera.
