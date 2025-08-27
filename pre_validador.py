
import io
import re
import unicodedata
from typing import List, Optional

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Validador 102 / Base", layout="wide")

# -----------------------------
# Utilidades
# -----------------------------
def norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def map_columns(df: pd.DataFrame) -> dict:
    return {norm(c): c for c in df.columns}

def find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    m = map_columns(df)
    for alias in candidates:
        n = norm(alias)
        if n in m:
            return m[n]
    return None

def read_excel_file(uploaded) -> pd.DataFrame:
    return pd.read_excel(uploaded, dtype=str, engine="openpyxl")

def to_str_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip()

def parse_date_series(s: pd.Series) -> pd.Series:
    # Intenta convertir a fecha y formatear como dd/mm/yyyy
    parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")
    out = parsed.dt.strftime("%d/%m/%Y")
    # Cuando no es parseable, deja el valor original
    out = out.fillna(s)
    return out

def concat_prefijo_sufijo(prefijo: pd.Series, sufijo: pd.Series) -> pd.Series:
    return to_str_series(prefijo).fillna("") + to_str_series(sufijo).fillna("")

def any_violations(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    mask = False
    for c in cols:
        mask = mask | (df[c].fillna("") != "")
    return mask

# -----------------------------
# UI
# -----------------------------
st.title("🧪 Validador de Base vs Archivo 102")

st.markdown("""
Sube los cuatro archivos en **Excel**:

1) **Base principal** (contiene: `radicado_sistema_integral`, `fecha_factura`, `prefijo`, `sufijo`, `factura`)
2) **Archivo 102** (contiene: `FECHA_FACTURA`, `PREFIJO_FACTURA`, `NRO_FACTURA`, opcional `FACTURA` y, ojalá, el mismo `radicado_sistema_integral`)
3) **CIE10** (para futuras validaciones)
4) **MAPPIS** (para futuras validaciones)
""")

col1, col2 = st.columns(2)
with col1:
    base_file = st.file_uploader("📄 Base principal (.xlsx)", type=["xlsx", "xls"])
    cie10_file = st.file_uploader("📚 CIE10 (.xlsx)", type=["xlsx", "xls"])
with col2:
    a102_file = st.file_uploader("📄 Archivo 102 (.xlsx)", type=["xlsx", "xls"])
    mappis_file = st.file_uploader("🧭 MAPPIS (.xlsx)", type=["xlsx", "xls"])

do_run = st.button("🔍 Ejecutar validaciones", type="primary", use_container_width=True)

# -----------------------------
# Lógica
# -----------------------------
if do_run:
    if not base_file or not a102_file:
        st.error("Debes subir **Base principal** y **Archivo 102** al menos.")
        st.stop()

    try:
        df_base = read_excel_file(base_file)
    except Exception as e:
        st.exception(e)
        st.stop()

    try:
        df_102 = read_excel_file(a102_file)
    except Exception as e:
        st.exception(e)
        st.stop()

    # CIE10 y MAPPIS (no usados aún, solo se cargan)
    df_cie10 = None
    if cie10_file:
        try:
            df_cie10 = read_excel_file(cie10_file)
        except Exception as e:
            st.warning(f"No se pudo leer CIE10: {e}")

    df_mappis = None
    if mappis_file:
        try:
            df_mappis = read_excel_file(mappis_file)
        except Exception as e:
            st.warning(f"No se pudo leer MAPPIS: {e}")

    # Resolver nombres de columnas en Base
    col_radicado_b = find_col(df_base, ["radicado_sistema_integral", "radicado", "radicado_sistema"])
    col_fecha_b    = find_col(df_base, ["fecha_factura", "fecha de factura", "fec_factura"])
    col_prefijo_b  = find_col(df_base, ["prefijo"])
    col_sufijo_b   = find_col(df_base, ["consecutivo_factura", "numero", "nro"])
    col_factura_b  = find_col(df_base, ["factura", "nro_factura", "numero_factura"])

    required_base = {
        "radicado_sistema_integral": col_radicado_b,
        "fecha_factura": col_fecha_b,
        "prefijo": col_prefijo_b,
        "consecutivo_factura": col_sufijo_b,
        "factura": col_factura_b,
    }
    missing_base = [k for k, v in required_base.items() if v is None]
    if missing_base:
        st.error(f"En **Base** faltan columnas requeridas: {', '.join(missing_base)}")
        st.stop()

    # Resolver nombres de columnas en 102
    col_radicado_102 = find_col(df_102, ["radicado_sistema_integral", "radicado", "radicado_sistema"])
    col_fecha_102    = find_col(df_102, ["fecha_factura", "fecha de factura", "fec_factura", "fecha"])
    col_prefijo_102  = find_col(df_102, ["prefijo_factura", "prefijo"])
    col_nro_102      = find_col(df_102, ["nro_factura", "numero_factura", "AXA_FECHA_EXP_CENTRALIZADA", "numero", "nro"])
    col_factura_102  = find_col(df_102, ["factura", "no_factura", "num_factura"])

    info_cols_102 = []
    for label, col in [
        ("RADICADO_102", col_radicado_102),
        ("FECHA_FACTURA_102", col_fecha_102),
        ("PREFIJO_FACTURA_102", col_prefijo_102),
        ("NRO_FACTURA_102", col_nro_102),
        ("FACTURA_102", col_factura_102),
    ]:
        info_cols_102.append(f"{label}: {col if col else 'NO ENCONTRADA'}")

    with st.expander("Ver columnas encontradas"):
        st.write("Base:", required_base)
        st.write("102:", ";  ".join(info_cols_102))

    # Normalizar/derivar columnas necesarias
    base = df_base.copy()

    base["_prefijo_s"] = to_str_series(base[col_prefijo_b])
    base["_sufijo_s"]  = to_str_series(base[col_sufijo_b])
    base["_factura_s"] = to_str_series(base[col_factura_b])
    base["_radicado_s"] = to_str_series(base[col_radicado_b])
    base["_fecha_orig"] = to_str_series(base[col_fecha_b])
    base["_fecha_fmt"]  = parse_date_series(base["_fecha_orig"])

    # Preparar 102 con columnas esperadas
    a102 = df_102.copy()
    if col_prefijo_102 is not None:
        a102["_prefijo_s"] = to_str_series(a102[col_prefijo_102])
    else:
        a102["_prefijo_s"] = ""

    if col_nro_102 is not None:
        a102["_nro_s"] = to_str_series(a102[col_nro_102])
    else:
        a102["_nro_s"] = ""

    if col_factura_102 is not None:
        a102["_factura_102_s"] = to_str_series(a102[col_factura_102])
    else:
        # Si no existe FACTURA en 102, construimos con PREFIJO+NRO
        a102["_factura_102_s"] = a102["_prefijo_s"] + a102["_nro_s"]

    if col_radicado_102 is not None:
        a102["_radicado_s"] = to_str_series(a102[col_radicado_102])
    else:
        # Si 102 no tiene radicado, igual creamos para evitar errores (join no funcionará)
        a102["_radicado_s"] = ""

    if col_fecha_102 is not None:
        a102["_fecha_fmt"] = parse_date_series(to_str_series(a102[col_fecha_102]))
    else:
        a102["_fecha_fmt"] = ""

    # Deduplicar 102 por radicado (si existe)
    if col_radicado_102 is not None and col_radicado_102 in a102.columns:
        a102 = a102.sort_index().drop_duplicates(subset=["_radicado_s"], keep="last")

    # Join Base x 102 por radicado
    merged = base.merge(
        a102[["_radicado_s", "_fecha_fmt", "_prefijo_s", "_nro_s", "_factura_102_s"]],
        on="_radicado_s",
        how="left",
        suffixes=("", "_102"),
    )

    # Validaciones
    # 1) fecha_factura Base (formato dd/mm/yyyy) vs FECHA_FACTURA en 102
    merged["VAL_FECHA_FACTURA"] = np.where(
        (merged["_fecha_fmt"].notna()) & (merged["_fecha_fmt"] != merged["_fecha_fmt_102"]) & merged["_fecha_fmt_102"].notna(),
        "NO CORRESPONDE LA FECHA FACTURA ORIGINAL CON LA FECHA FACTURA DE LA 102",
        ""
    )

    # 2) prefijo/sufijo Base vs PREFIJO_FACTURA/NRO_FACTURA en 102
    merged["VAL_PREFIJO"] = np.where(
        (merged["_prefijo_s"].notna()) & (merged["_prefijo_s_102"].notna()) & (merged["_prefijo_s"] != merged["_prefijo_s_102"]),
        "prefijo no coincide con la 102",
        ""
    )
    merged["VAL_SUFIJO"] = np.where(
        (merged["_sufijo_s"].notna()) & (merged["_nro_s"].notna()) & (merged["_sufijo_s"] != merged["_nro_s"]),
        "sufijo no coincide con la 102",
        ""
    )

    # 3) (prefijo + sufijo) vs FACTURA de la Base
    merged["_prefijo_sufijo"] = merged["_prefijo_s"] + merged["_sufijo_s"]
    merged["VAL_FACTURA_BASE"] = np.where(
        (merged["_factura_s"].notna()) & (merged["_prefijo_sufijo"].notna()) & (merged["_prefijo_sufijo"] != merged["_factura_s"]),
        "prefijo + sufijo no es igual a la factura",
        ""
    )

    # 4) (prefijo + sufijo) vs FACTURA de la 102
    merged["VAL_FACTURA_102"] = np.where(
        (merged["_prefijo_sufijo"].notna()) & (merged["_factura_102_s"].notna()) & (merged["_prefijo_sufijo"] != merged["_factura_102_s"]),
        "prefijo + sufijo no es igual a la factura (102)",
        ""
    )

    # Columnas de salida (mantener Base + validaciones)
    val_cols = ["VAL_FECHA_FACTURA", "VAL_PREFIJO", "VAL_SUFIJO", "VAL_FACTURA_BASE", "VAL_FACTURA_102"]
    # Mantener nombres originales de la base al frente
    out_cols = list(df_base.columns) + val_cols

    # Algunos pueden no existir si el merge cambió nombres; asegurar su presencia
    for c in val_cols:
        if c not in merged.columns:
            merged[c] = ""

    resultado = merged[out_cols].copy()

    st.success("Validaciones ejecutadas.")
    with st.expander("Ver muestra de la tabla completa (primeras 200 filas)"):
        st.dataframe(resultado.head(200), use_container_width=True)

    # Solo filas con alguna observación
    errores_mask = any_violations(resultado, val_cols)
    errores = resultado.loc[errores_mask].copy()
    st.subheader("🔎 Filas con observaciones")
    st.dataframe(errores.head(500), use_container_width=True)

    # Resumen de conteos
    st.subheader("📊 Resumen")
    counts = {c: int((resultado[c].fillna("") != "").sum()) for c in val_cols}
    st.write(counts)

    # Exportar a Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resultado.to_excel(writer, index=False, sheet_name="Resultado")
        errores.to_excel(writer, index=False, sheet_name="Observaciones")
        # También incluimos una hoja con mapeo de columnas detectadas
        cols_info = pd.DataFrame({
            "Base (requeridas)": list(required_base.keys()),
            "Detectada": list(required_base.values())
        })
        info_102 = pd.DataFrame({
            "102 (claves)": ["radicado", "fecha_factura", "prefijo_factura", "nro_factura", "factura"],
            "Detectada": [col_radicado_102, col_fecha_102, col_prefijo_102, col_nro_102, col_factura_102]
        })
        cols_info.to_excel(writer, index=False, sheet_name="InfoColumnas_Base")
        info_102.to_excel(writer, index=False, sheet_name="InfoColumnas_102")

    st.download_button(
        label="⬇️ Descargar resultado (Excel)",
        data=buffer.getvalue(),
        file_name="resultado_validaciones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # Informativo sobre CIE10 y MAPPIS
    with st.expander("Estado de CIE10 / MAPPIS (para futuras validaciones)"):
        if df_cie10 is not None:
            st.write(f"CIE10 cargado: {df_cie10.shape[0]} filas, {df_cie10.shape[1]} columnas.")
        else:
            st.write("CIE10 no cargado.")
        if df_mappis is not None:
            st.write(f"MAPPIS cargado: {df_mappis.shape[0]} filas, {df_mappis.shape[1]} columnas.")
        else:
            st.write("MAPPIS no cargado.")
