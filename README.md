# Market News Terminal

MVP diario para buscar noticias bursátiles, evaluar su impacto fundamental y estimar su relevancia para SPY. Combina:

- Noticias de compañías mediante Finnhub cuando hay una clave configurada.
- Filings oficiales de SEC EDGAR.
- Noticias disponibles mediante `yfinance` como respaldo.
- Datos de mercado para SPY, QQQ, IWM, VIX, rendimiento del Treasury a 10 años, dólar y petróleo.
- Análisis estructurado con OpenAI cuando existe `OPENAI_API_KEY`.
- Motor de reglas transparente cuando no existe una clave de IA.
- Historial local en SQLite para futuras evaluaciones y calibración.

## 1. Instalación

Requiere Python 3.11 o superior.

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

## 2. Claves y configuración

Edita `.env`:

- `FINNHUB_API_KEY`: opcional. Aumenta la cobertura de noticias por ticker.
- `OPENAI_API_KEY`: opcional. Activa análisis semántico estructurado.
- `OPENAI_MODEL`: modelo usado para el clasificador.
- `SEC_USER_AGENT`: coloca un correo real. La SEC solicita identificación responsable para peticiones automatizadas.

La aplicación funciona sin Finnhub y sin OpenAI, pero entra en modo de respaldo y su precisión disminuye.


## Interfaz visual

La página incluye un tema oscuro personalizado y cuatro vistas:

- **Radar:** gráfico impacto vs. calidad del trade y ranking de señales.
- **Feed visual:** tarjetas de noticias con badges, tesis y puntajes.
- **SPY & macro:** pulso de SPY, QQQ, IWM, VIX, US10Y y DXY, además de un medidor de sesgo agregado.
- **Historial y calibración:** predicciones guardadas y precisión posterior a 1, 3 y 5 sesiones.

La configuración del tema está en `.streamlit/config.toml`; los componentes visuales y estilos están centralizados en `app.py`.

## 3. Interpretación de puntajes

- **Empresa (-100 a +100):** impacto fundamental estimado para el ticker.
- **SPY (-100 a +100):** impacto estimado sobre el índice, no sobre el ticker.
- **Confirmación (0 a 100):** cuánto coincide la reacción reciente del mercado con la dirección de la noticia.
- **Trade (0 a 100):** mezcla de impacto, fuente, novedad, confianza, confirmación y riesgo de que ya esté descontada.

Un puntaje alto no significa “comprar”. Significa que merece revisión prioritaria.


## 4. Escaneo diario automático

Edita `watchlist.txt` y ejecuta:

Windows:

```bash
run_daily_scan_windows.bat
```

macOS/Linux:

```bash
./run_daily_scan_mac_linux.sh
```

El proceso crea reportes CSV y HTML dentro de `reports/`. Puedes programar ese script con Windows Task Scheduler o `cron`. Los umbrales se controlan con `DAILY_LOOKBACK_DAYS`, `DAILY_MAX_NEWS_PER_TICKER` y `DAILY_MIN_TRADE_QUALITY` en `.env`.

## 5. Precisión: límites importantes

Este sistema no puede saber con certeza si una acción subirá o bajará. Los errores más comunes serán:

1. El titular omite condiciones económicas relevantes.
2. La noticia ya estaba descontada en el precio.
3. El mercado reacciona por macro, posicionamiento u opciones, no por el catalizador.
4. La noticia afecta de forma distinta a competidores, proveedores y clientes.
5. Datos gratuitos pueden tener retrasos, huecos o cambios de formato.

Para una versión de producción conviene contratar una fuente licenciada de noticias y mercado, guardar el texto completo autorizado, añadir consenso de analistas y ejecutar backtests por tipo de evento.

## 6. Próxima fase recomendada

- Medir retornos a 30 minutos, cierre, 1, 3 y 5 días después de cada noticia.
- Calibrar puntajes por ticker y tipo de evento.
- Añadir calendario macro y earnings.
- Incorporar datos de opciones/GEX de un proveedor autorizado.
- Enviar alertas solo cuando fuente, impacto y confirmación superen umbrales definidos.

## Aviso

Herramienta educativa y de investigación. No constituye asesoría financiera ni garantiza resultados.
