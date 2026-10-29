import streamlit as st
import pandas as pd
import io
from scipy import stats
import scikit_posthocs as sp
import plotly.express as px

# ページ設定
st.set_page_config(page_title="ノンパラ検定アプリ", layout="wide")
st.title("🌾 ノンパラメトリック検定 & 多重比較アプリ")

# ── サンプルデータ ──────────────────────────────────────────────────────────────
SAMPLE_DATA = (
    "肥料\t病害スコア\n"
    "A肥料\t1\n"
    "A肥料\t2\n"
    "A肥料\t1\n"
    "A肥料\t1\n"
    "A肥料\t2\n"
    "A肥料\t1\n"
    "B肥料\t4\n"
    "B肥料\t5\n"
    "B肥料\t4\n"
    "B肥料\t3\n"
    "B肥料\t5\n"
    "B肥料\t4\n"
    "C肥料\t2\n"
    "C肥料\t3\n"
    "C肥料\t2\n"
    "C肥料\t4\n"
    "C肥料\t3\n"
    "C肥料\t2"
)

# ── session_state 初期化 ──────────────────────────────────────────────────────
# text_area の key に直接連動させることで、確実に入力欄を書き換えます
if "input_data" not in st.session_state:
    st.session_state.input_data = ""

def load_sample():
    st.session_state.input_data = SAMPLE_DATA

# ── タブ構成 ───────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 データ分析ツール", "📖 ノンパラ検定とは？（農業向け解説）"])

with tab1:
    st.markdown("""
    ### 使い方
    1. Excelでデータ範囲をコピーして貼り付けるか、**「サンプルデータを読み込む」**を押してください。
    2. 対応ありデータ（同一個体の繰り返し測定）の場合は「対応あり」を選択してください。
    """)

    st.button("🌱 農業のサンプルデータを読み込む", on_click=load_sample)

    # key="input_data" を指定し、セッションステートと連動
    paste_data = st.text_area(
        "ここにExcelのデータを貼り付けてください",
        key="input_data",
        height=200,
        placeholder="群\t数値\nA肥料\t1\nA肥料\t2...",
    )

    if paste_data.strip():
        try:
            # ── データ読み込み ─────────────────────────────────────────────────
            # まずタブ区切りで試す
            df = pd.read_csv(io.StringIO(paste_data), sep="\t")
            if len(df.columns) < 2:
                # タブ区切りでダメなら空白区切りでリトライ
                df = pd.read_csv(io.StringIO(paste_data), sep=r"\s+", engine="python")

            st.write("### 読み込まれたデータ（先頭5行）")
            st.dataframe(df.head())

            columns = df.columns.tolist()
            if len(columns) < 2:
                st.error("エラー: データが正しく区切られていません。Excelからコピーし直すか、1行目に列名があるか確認してください。")
                st.stop()

            # ── 列選択 ────────────────────────────────────────────────────────
            col1, col2, col3 = st.columns(3)
            with col1:
                group_col = st.selectbox("「群（グループ）」の列", columns, index=0)
            with col2:
                value_col = st.selectbox("「数値（測定値）」の列", columns, index=1)
            with col3:
                paired = st.radio(
                    "対応の有無",
                    ["対応なし", "対応あり"],
                    help="同一個体の繰り返し測定（前後比較など）は「対応あり」を選択",
                )

            if st.button("検定とグラフ作成を実行する", type="primary"):
                st.write("---")

                # ── 前処理 ────────────────────────────────────────────────────
                clean_df = df[[group_col, value_col]].copy()
                n_before = len(clean_df)
                # 数値列に変換（文字列などが混ざっていたらNaNにする）
                clean_df[value_col] = pd.to_numeric(clean_df[value_col], errors="coerce")
                clean_df = clean_df.dropna()
                n_after = len(clean_df)

                if n_before != n_after:
                    st.warning(f"⚠️ {n_before - n_after} 行を数値変換できなかったため除外しました（{n_after} 行を使用）。")

                # グループを出現順で固定（ソートしない：入力順を尊重）
                groups = list(dict.fromkeys(clean_df[group_col].tolist()))
                group_data = [clean_df[clean_df[group_col] == g][value_col].values for g in groups]
                num_groups = len(groups)

                if num_groups < 2:
                    st.error("エラー: 比較するためには2つ以上の群が必要です。")
                    st.stop()

                # ── 検定 ──────────────────────────────────────────────────────
                cld_series = pd.Series(dtype=str)
                overall_p_val = 1.0
                test_name = ""
                posthoc_df = None

                if num_groups == 2:
                    if paired == "対応あり":
                        test_name = "ウィルコクソン符号順位検定（対応あり）"
                        if len(group_data[0]) != len(group_data[1]):
                            st.error("エラー: 対応ありの場合、各群のデータ数が同じである必要があります。")
                            st.stop()
                        stat, overall_p_val = stats.wilcoxon(group_data[0], group_data[1])
                    else:
                        test_name = "マン・ホイットニーのU検定（対応なし）"
                        stat, overall_p_val = stats.mannwhitneyu(
                            group_data[0], group_data[1], alternative="two-sided"
                        )
                else:
                    if paired == "対応あり":
                        test_name = "フリードマン検定（対応あり）"
                        try:
                            stat, overall_p_val = stats.friedmanchisquare(*group_data)
                        except Exception as e:
                            st.error(f"フリードマン検定エラー: {e}\n各群のデータ数が同じか確認してください。")
                            st.stop()
                    else:
                        test_name = "クラスカル・ウォリス検定（対応なし）"
                        stat, overall_p_val = stats.kruskal(*group_data)

                    # ── 事後検定（Steel-Dwass）+ CLD ──────────────────────────
                    if overall_p_val < 0.05:
                        try:
                            posthoc_df = sp.posthoc_dscf(
                                clean_df, val_col=value_col, group_col=group_col
                            )
                            cld_series = sp.compact_letter_display(
                                posthoc_df, alpha=0.05
                            ).str.strip()
                        except Exception as e:
                            st.warning(f"多重比較（事後検定）の計算中にエラーが発生しました: {e}")

                # ── グラフ ────────────────────────────────────────────────────
                st.write("### 📈 データの分布と検定結果")
                fig = px.box(
                    clean_df,
                    x=group_col,
                    y=value_col,
                    color=group_col,
                    points="all",
                    category_orders={group_col: groups},  # 入力順を維持
                    title=f"{group_col} ごとの {value_col} の分布",
                )
                fig.update_layout(showlegend=False)

                if not cld_series.empty:
                    y_min = clean_df[value_col].min()
                    y_max = clean_df[value_col].max()
                    y_range = y_max - y_min
                    margin = y_range * 0.12 if y_range > 0 else 0.5

                    for g in groups:
                        if g in cld_series.index:
                            g_max = clean_df[clean_df[group_col] == g][value_col].max()
                            fig.add_annotation(
                                x=g,
                                y=g_max + margin,
                                text=f"<b>{cld_series[g]}</b>",
                                showarrow=False,
                                font=dict(size=18, color="black"),
                            )
                    fig.update_yaxes(
                        range=[y_min - margin, y_max + margin * 3]
                    )

                st.plotly_chart(fig, use_container_width=True)

                # ── 統計詳細 ──────────────────────────────────────────────────
                st.write("---")
                st.write("### 📊 統計検定の詳細")
                st.write(f"#### 全体検定: {test_name}")

                m1, m2 = st.columns(2)
                with m1:
                    st.metric("全体検定のp値", f"{overall_p_val:.4f}")
                with m2:
                    # 効果量（順位相関 r = Z / √N）
                    if num_groups == 2:
                        n_total = sum(len(g) for g in group_data)
                        if paired == "対応あり":
                            # p値が1.0の場合などのゼロ除算や無限大エラーを回避
                            p_val_adj = max(overall_p_val, 1e-15)
                            z = stats.norm.ppf(p_val_adj / 2)
                        else:
                            z_stat, _ = stats.mannwhitneyu(
                                group_data[0], group_data[1], alternative="two-sided"
                            )
                            n1, n2 = len(group_data[0]), len(group_data[1])
                            mu = n1 * n2 / 2
                            sigma = ((n1 * n2 * (n1 + n2 + 1)) / 12) ** 0.5
                            z = (z_stat - mu) / sigma if sigma > 0 else 0
                            
                        r = abs(z) / (n_total ** 0.5)
                        st.metric("効果量 r", f"{r:.3f}", help="|r| : 0.1=小, 0.3=中, 0.5=大")

                if overall_p_val < 0.05:
                    st.success("🌟 5%水準で有意な差があります。")
                    if num_groups > 2 and posthoc_df is not None:
                        st.write("#### 🔗 Steel-Dwass 検定（総当たり p 値マトリックス）")
                        
                        def highlight_sig(val):
                            if isinstance(val, float) and val < 0.05 and val != 1.0:
                                return "background-color: #ffe0e0; font-weight: bold"
                            return ""

                        # Pandas 2.1 以降でのエラー対策（applymap は map に変更された）
                        styled_df = posthoc_df.style.format("{:.4f}")
                        if hasattr(styled_df, "map"):
                            st.dataframe(styled_df.map(highlight_sig))
                        else:
                            st.dataframe(styled_df.applymap(highlight_sig))

                        if not cld_series.empty:
                            st.write("#### 🔤 Compact Letter Display (CLD)")
                            st.caption("同じ文字を共有する群の間に有意差なし")
                            cld_df = cld_series.to_frame(name="アルファベット判定")
                            cld_df.index.name = "群名"
                            st.dataframe(cld_df)
                else:
                    st.info("有意な差は見つかりませんでした（p ≥ 0.05）。")

        except Exception as e:
            st.error(f"データの読み込みまたは処理でエラーが発生しました: {e}")

# ── 解説タブ ──────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("""
    ## ノンパラメトリック検定とは？
    データが正規分布に従わない場合や、データ数が少ない場合でも使える統計手法です。
    データの値そのものではなく**「順位」**に変換して計算します。

    ### 検定の選択フロー

    | 群数 | 対応 | 検定手法 |
    |------|------|---------|
    | 2群 | なし | マン・ホイットニー U 検定 |
    | 2群 | あり | ウィルコクソン符号順位検定 |
    | 3群以上 | なし | クラスカル・ウォリス検定 → Steel-Dwass |
    | 3群以上 | あり | フリードマン検定 |

    ### 🌾 農業分野での活用シーン

    #### ① 病害の程度（発病度スコア）
    * **事例:** 「0＝健全、1＝微小な斑点、2＝葉の半分に病斑、3＝枯死」のような段階評価。
    * **理由:** スコア間の差が等間隔でない順序データのため。

    #### ② 食味の程度（官能評価）
    * **事例:** 「甘さ」「硬さ」「総合評価」の5段階アンケート。
    * **理由:** 外れ値が出やすい主観的評価に強い。

    #### ③ 色・等級（ランク分け）
    * **事例:** カラーチャートによる着色度「秀・優・良」や「レベル1〜10」。
    * **理由:** 数値ではなく順位としての意味が強いデータ。

    ### CLD（Compact Letter Display）の読み方
    * 異なる文字 → 有意差あり（例: a と b）
    * 同じ文字が含まれる → 有意差なし（例: ab と b は差なし）
    """)
