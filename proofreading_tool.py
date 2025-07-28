# proofreading_tool.py (完全版)

import streamlit as st
import re
import pandas as pd
from datetime import datetime
import io

# Google Generative AIライブラリのインポート
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- ページ設定 ---
st.set_page_config(
    page_title="台本誤字脱字チェックツール",
    page_icon="📝",
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


# --- カスタムCSS ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
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
    }
    .error-card {
        background-color: #fee;
        border-left-color: #e74c3c;
    }
    .suggestion-card {
        background-color: #fef9e7;
        border-left-color: #f39c12;
    }
    .info-card {
        background-color: #e8f4fd;
        border-left-color: #3498db;
    }
</style>
""", unsafe_allow_html=True)


# --- メインクラス ---
class ScriptProofreadingTool:
    def __init__(self):
        self.basic_patterns = [
            {'pattern': r'[。、]{2,}', 'type': '句読点重複', 'message': '句読点が重複しています'},
            {'pattern': r'[!?！？]{2,}', 'type': '感嘆符重複', 'message': '感嘆符や疑問符が重複しています'},
            {'pattern': r'\s{2,}', 'type': '空白重複', 'message': '不要な空白が連続しています'},
            {'pattern': r'[ａ-ｚＡ-Ｚ０-９]', 'type': '全角英数字', 'message': '全角英数字が使用されています。半角に統一することを推奨します'},
            {'pattern': r'という事', 'type': '表記統一', 'message': '「という事」はひらがなで「ということ」と書くのが一般的です'},
            {'pattern': r'いう事', 'type': '表記統一', 'message': '「いう事」はひらがなで「いうこと」と書くのが一般的です'},
            {'pattern': r'出来る', 'type': '表記統一', 'message': '補助動詞の「できる」はひらがなで書くのが一般的です'},
            {'pattern': r'無い', 'type': '表記統一', 'message': '補助形容詞の「ない」はひらがなで書くのが一般的です'},
            {'pattern': r'見れる', 'type': 'ら抜き言葉', 'message': '「見れる」は「見られる」が正しい表現です'},
            {'pattern': r'食べれる', 'type': 'ら抜き言葉', 'message': '「食べれる」は「食べられる」が正しい表現です'},
            {'pattern': r'です。ます。', 'type': '文体混在', 'message': '「ですます調」が不自然に連続している可能性があります'},
        ]

    def perform_basic_check(self, text):
        results = []
        lines = text.split('\n')
        for line_idx, line in enumerate(lines, 1):
            for pattern_info in self.basic_patterns:
                for match in re.finditer(pattern_info['pattern'], line):
                    results.append({
                        'type': pattern_info['type'], 'line': line_idx, 'position': match.start(),
                        'text': match.group(), 'message': pattern_info['message'], 'severity': 'suggestion'
                    })
            if len(line) > 100:
                results.append({
                    'type': '行長すぎ', 'line': line_idx, 'position': 0, 'text': line[:50] + '...',
                    'message': f'行が長すぎます（{len(line)}文字）。読みにくさを改善するため、改行を検討してください', 'severity': 'suggestion'
                })
            if '「' in line and '」' not in line:
                results.append({
                    'type': 'セリフ閉じ忘れ', 'line': line_idx, 'position': line.find('「'), 'text': '「',
                    'message': 'セリフの閉じ括弧「」」が見つかりません', 'severity': 'error'
                })
            if line.strip().startswith('「'):
                results.append({
                    'type': '話者不明の可能性', 'line': line_idx, 'position': 0, 'text': line.strip(),
                    'message': '行頭がセリフで始まっています。話者（キャラクター名やN：ナレーション）の指定が抜けている可能性があります',
                    'severity': 'suggestion'
                })
        return results

    def perform_ai_check(self, text, api_key):
        if not GENAI_AVAILABLE:
            st.error("Google Generative AIライブラリがロードされていません。")
            return []
        if not api_key:
            st.warning("AIチェックを実行するにはAPIキーが必要です。")
            return []

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"""以下の台本テキストをプロの校正者としてレビューしてください。
誤字脱字、文法的な誤り、表記の揺れ、不自然な言い回し、台本として不適切な箇所を厳しくチェックし、具体的な修正案を提示してください。
特に、**各セリフの前に話者（例：「田中」「N」など）が明記されているか**を確認し、話者が不明なセリフは必ず指摘してください。

【台本テキスト】
{text}

【出力形式】
発見した問題点について、以下の箇条書き形式（必ずハイフン `-` で始めてください）で回答してください。
問題が見つからない場合は「問題は見つかりませんでした。」とだけ回答してください。
---
- 種類: (誤字/表記揺れ/表現改善/話者不明/文法エラー/その他)
- 行番号: (問題がある箇所の行番号)
- 問題箇所: (原文のテキスト)
- 修正案: (具体的な修正案)
- 理由: (なぜ修正が必要なのか、その理由)
---
"""
            response = model.generate_content(prompt)
            return self.parse_ai_response(response.text)
        except Exception as e:
            st.error(f"AIチェック中にエラーが発生しました: {e}")
            return []

    def parse_ai_response(self, response_text):
        results = []
        # レスポンスを個々の指摘に分割
        issues = response_text.strip().split('---')
        for issue_block in issues:
            if not issue_block.strip():
                continue
            
            current_issue = {}
            for line in issue_block.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().replace('-', '').strip()
                    value = value.strip()

                    if key == "種類":
                        current_issue['type'] = value
                    elif key == "行番号":
                        try:
                            current_issue['line'] = int(re.search(r'\d+', value).group())
                        except (ValueError, AttributeError):
                            current_issue['line'] = 0 # 不明な場合は0
                    elif key == "問題箇所":
                        current_issue['text'] = value
                    elif key == "修正案":
                        current_issue['suggestion'] = value
                    elif key == "理由":
                        current_issue['reason'] = value

            if 'type' in current_issue and 'text' in current_issue:
                results.append(self.format_ai_result(current_issue))
        return results

    def format_ai_result(self, issue):
        msg = f"{issue.get('reason', 'N/A')}"
        if 'suggestion' in issue:
            msg += f"\n提案: 「{issue.get('suggestion')}」"
        
        # 'error'の基準を広げる
        error_types = ['誤字', '文法エラー', '脱字', 'セリフ閉じ忘れ']
        severity = 'error' if any(err_type in issue.get('type', '') for err_type in error_types) else 'suggestion'

        return {
            'type': f"AI: {issue.get('type', '指摘')}",
            'line': issue.get('line', 0),
            'position': 0,
            'text': issue.get('text', 'N/A'),
            'message': msg,
            'severity': severity
        }

# --- サイドバー ---
with st.sidebar:
    st.header("🔧 設定")
    api_key = st.text_input("Gemini API Key", type="password", help="https://makersuite.google.com/app/apikey で取得できます")

    if not GENAI_AVAILABLE:
        st.error("Google Generative AI ライブラリが読み込まれていません。")

    uploaded_file = st.file_uploader("📁 ファイルをアップロード (.txt)", type=['txt'])
    if uploaded_file is not None:
        try:
            # ファイルがアップロードされたら、session_stateを更新
            st.session_state['script_text'] = uploaded_file.read().decode("utf-8")
            st.success(f"'{uploaded_file.name}' を読み込みました。")
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")

    st.subheader("チェックオプション")
    use_basic_check = st.checkbox("基本チェック", value=True)
    # APIキーがない場合、AIチェックを無効化
    use_ai_check = st.checkbox("AI高精度チェック (Gemini)", value=bool(api_key and GENAI_AVAILABLE), disabled=not (api_key and GENAI_AVAILABLE))
    
    if not api_key and GENAI_AVAILABLE:
        st.info("AIチェックを利用するには、Gemini APIキーを入力してください。")

# --- メイン画面 ---
st.markdown('<h1 class="main-header">📝 台本誤字脱字チェックツール</h1>', unsafe_allow_html=True)
if not GENAI_AVAILABLE:
    st.warning("⚠️ 現在、AI機能が利用できません。基本チェックのみ実行可能です。")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 台本テキスト")
    # keyを設定して、st.session_stateとテキストエリアを接続
    st.text_area(
        "台本をここに貼り付けるか、左のサイドバーからファイルをアップロードしてください",
        height=450,
        key='script_text' # session_stateのキーと一致させる
    )

with col2:
    st.subheader("📊 チェック結果")
    if st.button("🔍 チェック実行", type="primary", use_container_width=True):
        if not st.session_state['script_text'].strip():
            st.warning("台本が入力されていません。")
        else:
            tool = ScriptProofreadingTool()
            all_results = []
            with st.spinner("チェックを実行中..."):
                if use_basic_check:
                    all_results.extend(tool.perform_basic_check(st.session_state['script_text']))
                if use_ai_check:
                    all_results.extend(tool.perform_ai_check(st.session_state['script_text'], api_key))
            
            # 結果をソート（行番号、重要度）
            all_results.sort(key=lambda x: (x['line'], x['severity'] == 'error'), reverse=False)
            st.session_state['results'] = all_results
            st.success(f"チェック完了！ {len(all_results)}件の指摘が見つかりました。")
            st.session_state['run_check'] = True # チェックが実行されたことを記録

# --- 結果表示エリア ---
if st.session_state['run_check']:
    results = st.session_state['results']
    script_text = st.session_state['script_text']

    st.subheader("📈 統計情報")
    errors = [r for r in results if r['severity'] == 'error']
    suggestions = [r for r in results if r['severity'] == 'suggestion']
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 重大な指摘", len(errors))
    c2.metric("🟡 改善提案", len(suggestions))
    c3.metric("総文字数", len(script_text))
    c4.metric("総行数", len(script_text.split('\n')))

    st.subheader("📋 詳細結果")
    if not results:
        st.success("🎉 素晴らしい！問題は見つかりませんでした。")
    else:
        tab_titles = [f"すべて ({len(results)})", f"🔴 重大な指摘 ({len(errors)})", f"🟡 改善提案 ({len(suggestions)})"]
        tab_all, tab_errors, tab_suggestions = st.tabs(tab_titles)

        def display_result(result, index):
            css_class = "error-card" if result['severity'] == 'error' else "suggestion-card"
            st.markdown(f"""
            <div class="result-card {css_class}">
                <strong>{index}. [{result['type']}] 行番号: {result['line'] or '不明'}</strong><br>
                <b>問題箇所:</b> <code>{st.runtime.scriptrunner.script_run_context.escape_html(result['text'])}</code><br>
                <b>詳細:</b> {st.runtime.scriptrunner.script_run_context.escape_html(result['message']).replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

        with tab_all:
            for i, r in enumerate(results, 1):
                display_result(r, i)
        with tab_errors:
            if not errors:
                st.info("重大な指摘はありませんでした。")
            for i, r in enumerate(errors, 1):
                display_result(r, i)
        with tab_suggestions:
            if not suggestions:
                st.info("改善提案はありませんでした。")
            for i, r in enumerate(suggestions, 1):
                display_result(r, i)

        # エクスポート機能
        st.subheader("📥 結果をエクスポート")
        df = pd.DataFrame(results)
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        
        e_col1, e_col2 = st.columns(2)
        with e_col1:
            st.download_button(
                "📊 CSV形式でダウンロード", csv, f"校正結果_{datetime.now():%Y%m%d_%H%M%S}.csv", "text/csv")
        with e_col2:
            txt_output = ""
            for r in results:
                txt_output += f"[{r['type']}] 行:{r['line']}\n問題箇所: {r['text']}\n詳細: {r['message']}\n\n"
            st.download_button(
                "📄 テキスト形式でダウンロード", txt_output, f"校正結果_{datetime.now():%Y%m%d_%H%M%S}.txt", "text/plain")


# --- フッター ---
st.markdown("---")
with st.expander("使い方と機能詳細"):
    st.markdown("""
    ### 使い方
    1. **APIキー設定**: (AIチェック利用時) サイドバーでGoogleのGemini APIキーを入力します。
    2. **台本入力**: テキストエリアに直接ペーストするか、`.txt`ファイルをアップロードします。
    3. **チェック実行**: `チェック実行`ボタンを押すと、設定したオプションで校正が始まります。
    4. **結果確認**: 結果が統計と詳細リストで表示されます。タブで重要度ごとに絞り込めます。
    5. **エクスポート**: 必要に応じて、結果をCSVまたはテキストファイルで保存できます。

    ### 機能詳細
    - **基本チェック**: 正規表現に基づき、句読点の重複や表記揺れなど、一般的な間違いを高速に検出します。
    - **AI高精度チェック**: Geminiモデルを活用し、文脈を理解した上での誤字脱字、不自然な表現、話者指定の漏れなどを指摘します。
    - **APIキーについて**: AIチェックはGoogleの生成AIサービスを利用します。キーは[Google AI Studio](https://makersuite.google.com/app/apikey)で無料で取得できます。キーはサーバーに保存されません。
    """)
st.markdown("💡 **ヒント**: APIキーがなくても、基本的なチェック機能はすべて無料で利用可能です。")
