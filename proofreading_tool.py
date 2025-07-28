# proofreading_tool_v2.py (台本作成機能 統合・完成版)

import streamlit as st
import re
import pandas as pd
from datetime import datetime
import io
import html # HTMLエスケープ用

# --- Google Generative AIライブラリのインポート ---
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- ページ設定 ---
st.set_page_config(
    page_title="AI台本作家 & 校正ツール",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State の初期化 ---
# アプリのリロード時に変数がリセットされるのを防ぐ
if 'results' not in st.session_state:
    st.session_state['results'] = []
if 'script_text' not in st.session_state:
    st.session_state['script_text'] = ""
if 'run_check' not in st.session_state:
    st.session_state['run_check'] = False
if 'generated_plot' not in st.session_state:
    st.session_state['generated_plot'] = ""
if 'generated_script' not in st.session_state:
    st.session_state['generated_script'] = ""

# --- カスタムCSS ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #84fab0 0%, #8fd3f4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3rem;
        font-weight: bold;
    }
    .result-card {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
        border-left: 4px solid;
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .error-card {
        background-color: #fff0f0;
        border-left-color: #e74c3c;
    }
    .suggestion-card {
        background-color: #fef9e7;
        border-left-color: #f39c12;
    }
</style>
""", unsafe_allow_html=True)


# --- AIロジッククラス ---
class AiAssistant:
    def __init__(self, api_key):
        if not GENAI_AVAILABLE or not api_key:
            raise ValueError("Gemini APIキーが設定されていないか、ライブラリが利用できません。")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def _generate(self, prompt):
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            st.error(f"AIとの通信中にエラーが発生しました: {str(e)}")
            return None

    def create_plot(self, genre, theme):
        prompt = f"""
あなたは、視聴者の心を掴む構成力に長けたプロの放送作家です。
以下のテーマとジャンルに基づき、YouTubeの2ch風まとめ動画用の、面白くて魅力的なプロットを作成してください。

# 指示
- 物語の「起承転結」が明確にわかるように構成してください。
- 主要な登場人物（イッチ、物語の中心となる人物など）を簡潔に設定してください。
- 視聴者がワクワクするような、意外な展開やスカッとするクライマックスを必ず含めてください。
- スレタイは視聴者のクリックを誘うような、魅力的で少し大げさなものにしてください。

# 入力
- ジャンル: {genre}
- テーマ: {theme}

# 出力形式
【スレタイ案】: （例：【衝撃】駅で倒れた婆さんを助けたら、とんでもないお礼をされた結果www）
【登場人物】
- イッチ: （特徴や性格）
- 〇〇: （他の登場人物の特徴）
【プロット】
- 起: （物語の始まり、イッチがスレを立てた状況）
- 承: （物語の展開、問題の発生や葛藤）
- 転: （事態の急変、クライマックスに向けた盛り上がり）
- 結: （物語の結末、オチ、イッチの感想や後日談）
"""
        return self._generate(prompt)

    def create_script(self, plot, length_minutes=8):
        prompt = f"""
あなたは、2ch（5ch）の空気感を完璧に再現できるプロのシナリオライターです。
以下のプロットとキャラクター設定に基づき、約{length_minutes}分の尺になるような、リアルで面白いYouTubeの2ch風動画台本を作成してください。

# 厳守すべきルール
- 必ず「N:」から始まるナレーションで台本を開始し、視聴者に状況を分かりやすく説明してください。
- 会話は「イッチ:」「名無しA:」「名無しB:」のように、誰のセリフか明確にわかる形式で記述してください。
- 2ch特有のネットスラング（例: www, 乙, 草, 激しく同意, kwsk）や顔文字（例: (´・ω・｀), ｷﾀ━━━━(ﾟ∀ﾟ)━━━━!!）を自然に、かつ効果的に使用してください。
- 名無しさんたちのレスには、イッチへの質問、共感、ツッコミ、的確なアドバイス、面白い煽りなどをバランス良く含め、スレが進行しているライブ感を演出してください。
- 物語の展開が分かりやすくなるように、適宜「N:」のナレーションで解説や補足を入れてください。
- 動画の演出を考慮し、画像やテロップを挿入してほしい箇所に【画像: 〇〇の写真】【テロップ: 衝撃の事実！】のような具体的な指示を挿入してください。
- 台本の最後は、ナレーションで物語を締めくくり、視聴者にチャンネル登録や高評価を促す言葉で綺麗に終わってください。（例：「この話が面白いと思ったら、高評価とチャンネル登録をお願いします！」）

# 入力情報
---
{plot}
---

# 出力
（ここに台本を生成）
"""
        return self._generate(prompt)


# --- 校正ツールクラス ---
class ScriptProofreadingTool:
    def __init__(self):
        self.basic_patterns = [
            {'pattern': r'[。、]{2,}', 'type': '句読点重複', 'message': '句読点が重複しています'},
            {'pattern': r'[!?！？]{2,}', 'type': '感嘆符重複', 'message': '感嘆符や疑問符が重複しています'},
            {'pattern': r'\s{2,}', 'type': '空白重複', 'message': '不要な空白が連続しています'},
            {'pattern': r'[ａ-ｚＡ-Ｚ０-９]', 'type': '全角英数字', 'message': '全角英数字が使用されています。半角に統一することを推奨します'},
            {'pattern': r'という事', 'type': '表記統一', 'message': '「という事」はひらがなで「ということ」と書くのが一般的です'},
            {'pattern': r'出来る', 'type': '表記統一', 'message': '補助動詞の「できる」はひらがなで書くのが一般的です'},
            {'pattern': r'見れる', 'type': 'ら抜き言葉', 'message': '「見れる」は「見られる」が正しい表現です'},
        ]

    def perform_basic_check(self, text):
        results = []
        lines = text.split('\n')
        for line_idx, line in enumerate(lines, 1):
            for pattern_info in self.basic_patterns:
                for match in re.finditer(pattern_info['pattern'], line):
                    results.append({'type': pattern_info['type'], 'line': line_idx, 'position': match.start(), 'text': match.group(), 'message': pattern_info['message'], 'severity': 'suggestion'})
            if '「' in line and '」' not in line:
                results.append({'type': 'セリフ閉じ忘れ', 'line': line_idx, 'position': line.find('「'), 'text': '「', 'message': 'セリフの閉じ括弧「」」が見つかりません', 'severity': 'error'})
        return results
    
    def perform_ai_check(self, text, api_key):
        try:
            assistant = AiAssistant(api_key)
            prompt = f"""あなたはプロの校正者です。以下のテキストをレビューし、誤字脱字、文法的な誤り、表記の揺れ、不自然な言い回しを指摘してください。
出力は問題点ごとに、必ず以下の形式のマークダウンで返してください。
---
- **種類**: (例: 誤字, 表記揺れ, 表現改善)
- **行番号**: (問題がある箇所の行番号)
- **問題箇所**: (原文のテキスト)
- **修正案**: (具体的な修正案)
- **理由**: (なぜ修正が必要なのか、その理由)
---
"""
            response = assistant._generate(prompt)
            return self.parse_ai_response(response) if response else []
        except ValueError as e:
            st.error(e)
            return []

    def parse_ai_response(self, response_text):
        results = []
        issues = response_text.strip().split('---')
        for issue_block in issues:
            if not issue_block.strip(): continue
            current_issue = {}
            for line in issue_block.strip().split('\n'):
                line = line.replace('**', '') # マークダウンの**を除去
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().replace('-', '').strip()
                    value = value.strip()
                    if key == "種類": current_issue['type'] = f"AI: {value}"
                    elif key == "行番号": current_issue['line'] = int(re.search(r'\d+', value).group()) if re.search(r'\d+', value) else 0
                    elif key == "問題箇所": current_issue['text'] = value
                    elif key == "修正案": current_issue['message'] = f"提案: {value}"
                    elif key == "理由": current_issue['message'] = f"{current_issue.get('message', '')} ({value})"
            if 'type' in current_issue:
                current_issue.setdefault('message', 'AIによる指摘')
                error_types = ['誤字', '文法エラー', '脱字']
                is_error = any(err_type in current_issue['type'] for err_type in error_types)
                current_issue['severity'] = 'error' if is_error else 'suggestion'
                results.append(current_issue)
        return results

# --- UI描画 ---
st.markdown('<h1 class="main-header">🎬 AI台本作家 & 校正ツール</h1>', unsafe_allow_html=True)

# --- サイドバー ---
with st.sidebar:
    st.header("🔑 APIキー設定")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studioで取得したAPIキーを入力してください。")
    if api_key:
        st.success("APIキーが設定されました。")
    else:
        st.warning("APIキーを入力すると全機能が利用可能になります。")
    
    st.info("このツールは入力されたAPIキーをサーバーに保存しません。", icon="🔒")
    st.markdown("---")
    st.header("📖 ツール説明")
    st.markdown("""
    **2ch風動画 台本作成**:
    - AIが2ch風の動画台本をプロットから作成します。
    - **フルオート**: テーマだけで全自動生成。
    - **セミオート**: プロットをAIと共同編集。
    - **持ち込み**: 既存プロットから台本化。

    **台本校正ツール**:
    - 完成した台本や自作の文章の誤字脱字、表現をチェックします。
    """)

# APIキーがなければ処理を中断
if not api_key:
    st.info("サイドバーからGemini APIキーを入力して、ツールを開始してください。", icon="👈")
    st.stop()

# --- メインコンテンツ ---
tab1, tab2 = st.tabs(["**📝 2ch風動画 台本作成**", "**🔍 台本校正ツール**"])

# --- タブ1: 台本作成 ---
with tab1:
    st.subheader("✍️ ステップ1: 制作モードを選択")
    mode = st.radio(
        "どの方法で台本を作成しますか？",
        ('フルオート', 'セミオート', '持ち込みプロット'),
        horizontal=True,
        captions=['テーマだけで全自動生成', 'AIと対話しつつ段階的に作成', '自作のプロットから台本化']
    )
    st.markdown("---")

    assistant = AiAssistant(api_key)

    if mode == 'フルオート':
        st.subheader("🚀 フルオートモード")
        with st.form("full_auto_form"):
            genre = st.selectbox("動画のジャンルを選択してください", ["スカッとする話", "修羅場", "感動する話", "DQN返し", "ほのぼの", "恋愛", "不思議な話"])
            theme = st.text_input("動画のテーマやキーワードを入力してください", placeholder="例：生意気な後輩を論破した")
            submitted = st.form_submit_button("プロットと台本を生成する", type="primary", use_container_width=True)

            if submitted and theme:
                with st.spinner("プロットを生成中..."):
                    plot = assistant.create_plot(genre, theme)
                    if plot:
                        st.session_state['generated_plot'] = plot
                        st.success("プロットが完成しました！続けて台本を生成します。")
                    else:
                        st.error("プロットの生成に失敗しました。")
                
                if st.session_state['generated_plot']:
                    st.text_area("生成されたプロット", value=st.session_state['generated_plot'], height=200, disabled=True)
                    with st.spinner("台本を生成中..."):
                        script = assistant.create_script(st.session_state['generated_plot'])
                        if script:
                            st.session_state['generated_script'] = script
                            st.success("台本が完成しました！")
                        else:
                            st.error("台本の生成に失敗しました。")
    
    elif mode == 'セミオート':
        st.subheader("🤝 セミオートモード")
        col1, col2 = st.columns(2)
        
        with col1:
            with st.form("semi_auto_plot_form"):
                st.markdown("##### ステップ2: プロットを生成")
                genre_semi = st.selectbox("動画のジャンル", ["スカッとする話", "修羅場", "感動する話", "DQN返し", "ほのぼの", "恋愛", "不思議な話"], key="genre_semi")
                theme_semi = st.text_input("動画のテーマやキーワード", placeholder="例：電車で絡んできた酔っぱらいを撃退", key="theme_semi")
                plot_submitted = st.form_submit_button("プロットを生成する")

                if plot_submitted and theme_semi:
                    with st.spinner("プロットを生成中..."):
                        plot = assistant.create_plot(genre_semi, theme_semi)
                        st.session_state['generated_plot'] = plot
            
            st.text_area("生成されたプロット（ここで編集できます）", height=300, key='generated_plot')

        with col2:
            st.markdown("##### ステップ3: 台本を生成")
            st.info("左側のプロットを自由に編集した後、下のボタンを押して台本を作成してください。")
            if st.button("このプロットで台本を生成する", type="primary", use_container_width=True):
                if st.session_state['generated_plot']:
                    with st.spinner("台本を生成中..."):
                        script = assistant.create_script(st.session_state['generated_plot'])
                        if script:
                            st.session_state['generated_script'] = script
                            st.success("台本が完成しました！")
                        else:
                            st.error("台本の生成に失敗しました。")
                else:
                    st.warning("先にプロットを生成または入力してください。")

    elif mode == '持ち込みプロット':
        st.subheader("📥 持ち込みプロットモード")
        st.text_area("ここに自作のプロットやアイデアを貼り付けてください", height=300, key='generated_plot')
        if st.button("このプロットで台本を生成する", type="primary", use_container_width=True):
            if st.session_state['generated_plot']:
                 with st.spinner("台本を生成中..."):
                    script = assistant.create_script(st.session_state['generated_plot'])
                    if script:
                        st.session_state['generated_script'] = script
                        st.success("台本が完成しました！")
                    else:
                        st.error("台本の生成に失敗しました。")
            else:
                st.warning("プロットを入力してください。")

    # 生成された台本の表示エリア
    if st.session_state['generated_script']:
        st.markdown("---")
        st.subheader("🎉 完成した台本")
        st.text_area("生成された台本（コピー＆ペーストして利用できます）", value=st.session_state['generated_script'], height=400)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 この台本を校正ツールに送る", use_container_width=True):
                st.session_state['script_text'] = st.session_state['generated_script']
                st.success("台本を校正ツールに転送しました。上の「台本校正ツール」タブに切り替えて確認してください。")
        with c2:
            st.download_button(
                label="💾 この台本をダウンロード (.txt)",
                data=st.session_state['generated_script'],
                file_name=f"台本_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )


# --- タブ2: 校正ツール ---
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 校正対象テキスト")
        st.text_area("ここにチェックしたい文章を入力するか、台本作成ツールから転送してください", height=400, key='script_text')
        
    with col2:
        st.subheader("⚙️ チェック実行")
        use_basic_check = st.checkbox("基本チェック（句読点・表記揺れなど）", value=True)
        use_ai_check = st.checkbox("AI高精度チェック（誤字脱字・表現改善）", value=True)
        
        if st.button("校正を実行する", type="primary", use_container_width=True):
            if not st.session_state['script_text'].strip():
                st.warning("校正するテキストを入力してください。")
            else:
                tool = ScriptProofreadingTool()
                all_results = []
                with st.spinner("チェック中..."):
                    if use_basic_check:
                        all_results.extend(tool.perform_basic_check(st.session_state['script_text']))
                    if use_ai_check:
                        all_results.extend(tool.perform_ai_check(st.session_state['script_text'], api_key))
                
                all_results.sort(key=lambda x: (x.get('line', 0), x.get('severity', 'suggestion') == 'error'), reverse=False)
                st.session_state['results'] = all_results
                st.session_state['run_check'] = True
                st.success("校正が完了しました！")

    if st.session_state['run_check']:
        st.markdown("---")
        st.subheader("📋 校正結果")
        results = st.session_state['results']
        if not results:
            st.success("🎉 素晴らしい！問題は見つかりませんでした。")
        else:
            errors = [r for r in results if r.get('severity') == 'error']
            suggestions = [r for r in results if r.get('severity') == 'suggestion']
            
            scol1, scol2 = st.columns(2)
            scol1.metric("🔴 重大な指摘 (要修正)", len(errors))
            scol2.metric("🟡 改善提案", len(suggestions))
            
            for i, r in enumerate(results, 1):
                css_class = "error-card" if r.get('severity') == 'error' else "suggestion-card"
                st.markdown(f"""
                <div class="result-card {css_class}">
                    <strong>{i}. [{r.get('type', '指摘')}] 行番号: {r.get('line', '不明')}</strong><br>
                    <b>問題箇所:</b> <code>{html.escape(r.get('text', ''))}</code><br>
                    <b>詳細:</b> {html.escape(r.get('message', '')).replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
