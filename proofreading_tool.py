import streamlit as st
import re
import pandas as pd
from datetime import datetime
import io

# Google Generative AIライブラリのインポート
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
    st.success("✅ Google Generative AI ライブラリが正常に読み込まれました")
except ImportError as e:
    GENAI_AVAILABLE = False
    st.error(f"❌ Google Generative AI ライブラリの読み込みに失敗: {str(e)}")
    st.info("requirements.txt の内容を確認してください")

# ページ設定
st.set_page_config(
    page_title="台本誤字脱字チェックツール",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
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
    
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# メインタイトル
st.markdown('<h1 class="main-header">📝 台本誤字脱字チェックツール</h1>', unsafe_allow_html=True)

class ScriptProofreadingTool:
    def __init__(self):
        self.basic_patterns = [
            {'pattern': r'[。、]{2,}', 'type': '句読点重複', 'message': '句読点が重複しています'},
            {'pattern': r'[！？]{2,}', 'type': '感嘆符重複', 'message': '感嘆符が重複しています'},
            {'pattern': r'\s{2,}', 'type': '空白重複', 'message': '空白が重複しています'},
            {'pattern': r'[ａ-ｚＡ-Ｚ０-９]', 'type': '全角英数字', 'message': '全角英数字が使用されています'},
            {'pattern': r'という事', 'type': '表記統一', 'message': '「という事」は「ということ」が適切です'},
            {'pattern': r'いう事', 'type': '表記統一', 'message': '「いう事」は「いうこと」が適切です'},
            {'pattern': r'出来る', 'type': '表記統一', 'message': '「出来る」は「できる」が適切です'},
            {'pattern': r'無い', 'type': '表記統一', 'message': '「無い」は「ない」が適切です'},
            {'pattern': r'見れる', 'type': '表記統一', 'message': '「見れる」は「見られる」が適切です'},
            {'pattern': r'食べれる', 'type': '表記統一', 'message': '「食べれる」は「食べられる」が適切です'},
            {'pattern': r'です。ます。', 'type': '敬語重複', 'message': '敬語が重複している可能性があります'},
        ]
    
    def perform_basic_check(self, text):
        """基本的な誤字脱字チェック"""
        results = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines, 1):
            # パターンチェック
            for pattern_info in self.basic_patterns:
                matches = re.finditer(pattern_info['pattern'], line)
                for match in matches:
                    results.append({
                        'type': pattern_info['type'],
                        'line': line_idx,
                        'position': match.start(),
                        'text': match.group(),
                        'message': pattern_info['message'],
                        'severity': 'error'
                    })
            
            # 行の長さチェック
            if len(line) > 100:
                results.append({
                    'type': '行長すぎ',
                    'line': line_idx,
                    'position': 0,
                    'text': line[:50] + '...' if len(line) > 50 else line,
                    'message': f'行が長すぎます（{len(line)}文字）',
                    'severity': 'suggestion'
                })
            
            # セリフの形式チェック
            if '「' in line and '」' not in line:
                results.append({
                    'type': 'セリフ未閉じ',
                    'line': line_idx,
                    'position': line.find('「'),
                    'text': '「',
                    'message': 'セリフの終わりの「」」が見つかりません',
                    'severity': 'error'
                })
        
        return results
    
    def perform_ai_check(self, text, api_key):
        """Gemini AIを使用した高精度チェック"""
        if not GENAI_AVAILABLE:
            st.error("Google Generative AIライブラリがインストールされていません。")
            return []
        
        if not api_key:
            return []
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            prompt = f"""以下の台本テキストを校正してください。誤字脱字、表記の統一、不自然な表現、台本として不適切な部分を指摘してください。

【台本テキスト】
{text}

【指摘形式】
各指摘について以下の形式で回答してください：
- 種類: （誤字/脱字/表記統一/表現改善/その他）
- 行番号: （該当する行番号）
- 問題箇所: （問題のある部分）
- 修正案: （修正提案）
- 理由: （修正理由）

台本として読みやすく、自然な日本語になるよう校正してください。"""
            
            response = model.generate_content(prompt)
            return self.parse_ai_response(response.text)
            
        except Exception as e:
            st.error(f"AI チェックでエラーが発生しました: {str(e)}")
            return []
    
    def parse_ai_response(self, response_text):
        """AIレスポンスを解析"""
        results = []
        lines = response_text.split('\n')
        current_issue = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('- 種類:'):
                if current_issue.get('type'):
                    results.append(self.format_ai_result(current_issue))
                current_issue = {'type': line.replace('- 種類:', '').strip()}
            elif line.startswith('- 行番号:'):
                try:
                    current_issue['line'] = int(re.search(r'\d+', line).group())
                except:
                    current_issue['line'] = 1
            elif line.startswith('- 問題箇所:'):
                current_issue['text'] = line.replace('- 問題箇所:', '').strip()
            elif line.startswith('- 修正案:'):
                current_issue['suggestion'] = line.replace('- 修正案:', '').strip()
            elif line.startswith('- 理由:'):
                current_issue['reason'] = line.replace('- 理由:', '').strip()
        
        if current_issue.get('type'):
            results.append(self.format_ai_result(current_issue))
        
        return results
    
    def format_ai_result(self, issue):
        """AI結果をフォーマット"""
        reason = issue.get('reason', '')
        suggestion = issue.get('suggestion', '')
        
        message_parts = []
        if reason:
            message_parts.append(reason)
        if suggestion:
            message_parts.append(f"提案: {suggestion}")
        
        return {
            'type': f"AI: {issue.get('type', '')}",
            'line': issue.get('line', 1),
            'position': 0,
            'text': issue.get('text', ''),
            'message': ' '.join(message_parts),
            'severity': 'error' if issue.get('type') in ['誤字', '脱字'] else 'suggestion'
        }

# サイドバー設定
with st.sidebar:
    st.header("🔧 設定")
    
    # API Key設定
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="https://makersuite.google.com/app/apikey で取得できます"
    )
    
    # ファイルアップロード
    uploaded_file = st.file_uploader(
        "📁 ファイルをアップロード",
        type=['txt'],
        help="テキストファイルをアップロードできます"
    )
    
    # チェックオプション
    st.subheader("チェックオプション")
    use_basic_check = st.checkbox("基本チェック", value=True)
    use_ai_check = st.checkbox("AIチェック", value=bool(api_key and GENAI_AVAILABLE))
    
    if not GENAI_AVAILABLE:
        st.warning("⚠️ AI機能が利用できません。アプリを再起動してみてください。")
        st.info("Streamlit Cloud: 右上の⋮メニューから「Reboot app」を選択")
    elif not api_key and use_ai_check:
        st.warning("AIチェックにはAPI Keyが必要です")

# メインエリア
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📄 台本テキスト")
    
    # ファイルが読み込まれた場合
    script_text = ""
    if uploaded_file is not None:
        try:
            script_text = str(uploaded_file.read(), "utf-8")
            st.success(f"ファイル '{uploaded_file.name}' を読み込みました")
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {str(e)}")
    
    # テキストエリア
    script_input = st.text_area(
        "台本を入力してください",
        value=script_text,
        height=400,
        help="台本のテキストを直接入力するか、左側でファイルをアップロードしてください"
    )

with col2:
    st.subheader("📊 チェック結果")
    
    if st.button("🔍 チェック実行", type="primary", use_container_width=True):
        if not script_input.strip():
            st.warning("台本テキストを入力してください。")
        else:
            # ツール初期化
            tool = ScriptProofreadingTool()
            all_results = []
            
            with st.spinner("チェック中..."):
                # 基本チェック
                if use_basic_check:
                    basic_results = tool.perform_basic_check(script_input)
                    all_results.extend(basic_results)
                
                # AIチェック
                if use_ai_check and api_key and GENAI_AVAILABLE:
                    ai_results = tool.perform_ai_check(script_input, api_key)
                    all_results.extend(ai_results)
            
            # セッションステートに保存
            st.session_state['results'] = all_results
            st.session_state['script_text'] = script_input
            st.success("チェックが完了しました！")

# 結果表示
if 'results' in st.session_state:
    results = st.session_state['results']
    script_text = st.session_state['script_text']
    
    # 統計情報
    st.subheader("📈 統計情報")
    
    errors = [r for r in results if r['severity'] == 'error']
    suggestions = [r for r in results if r['severity'] == 'suggestion']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("誤字脱字", len(errors))
    with col2:
        st.metric("改善提案", len(suggestions))
    with col3:
        st.metric("総文字数", len(script_text))
    with col4:
        st.metric("行数", len(script_text.split('\n')))
    
    # 詳細結果
    st.subheader("📋 詳細結果")
    
    if not results:
        st.success("🎉 問題は見つかりませんでした！")
    else:
        # 結果をタブで分類
        tab1, tab2, tab3 = st.tabs(["すべて", "誤字脱字", "改善提案"])
        
        with tab1:
            for i, result in enumerate(results, 1):
                css_class = "error-card" if result['severity'] == 'error' else "suggestion-card"
                st.markdown(f"""
                <div class="result-card {css_class}">
                    <strong>{i}. [{result['type']}] 行{result['line']}</strong><br>
                    問題箇所: <code>{result['text']}</code><br>
                    詳細: {result['message']}
                </div>
                """, unsafe_allow_html=True)
        
        with tab2:
            error_results = [r for r in results if r['severity'] == 'error']
            if error_results:
                for i, result in enumerate(error_results, 1):
                    st.markdown(f"""
                    <div class="result-card error-card">
                        <strong>{i}. [{result['type']}] 行{result['line']}</strong><br>
                        問題箇所: <code>{result['text']}</code><br>
                        詳細: {result['message']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("誤字脱字は見つかりませんでした。")
        
        with tab3:
            suggestion_results = [r for r in results if r['severity'] == 'suggestion']
            if suggestion_results:
                for i, result in enumerate(suggestion_results, 1):
                    st.markdown(f"""
                    <div class="result-card suggestion-card">
                        <strong>{i}. [{result['type']}] 行{result['line']}</strong><br>
                        問題箇所: <code>{result['text']}</code><br>
                        詳細: {result['message']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("改善提案はありません。")
        
        # 結果エクスポート
        st.subheader("📥 結果エクスポート")
        
        # DataFrame作成
        df = pd.DataFrame(results)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV エクスポート
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📊 CSV形式でダウンロード",
                data=csv,
                file_name=f"台本校正結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # テキスト形式エクスポート
            text_output = f"台本校正結果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            for i, result in enumerate(results, 1):
                text_output += f"{i}. [{result['type']}] 行{result['line']}\n"
                text_output += f"   問題箇所: {result['text']}\n"
                text_output += f"   詳細: {result['message']}\n\n"
            
            st.download_button(
                label="📄 テキスト形式でダウンロード",
                data=text_output,
                file_name=f"台本校正結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

# フッター情報
st.markdown("---")
with st.expander("📚 機能説明・使い方"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🔍 機能説明
        
        **基本チェック機能:**
        - 句読点・感嘆符の重複検出
        - 空白の重複チェック
        - 全角英数字の検出
        - 表記統一チェック（「出来る」→「できる」等）
        - 行の長さチェック
        - セリフの形式チェック
        
        **AI機能（Gemini 2.0 Flash）:**
        - 高精度な誤字脱字検出
        - 表記統一の提案
        - 不自然な表現の指摘
        - 台本として適切な修正提案
        """)
    
    with col2:
        st.markdown("""
        ### 📖 使い方
        
        1. **API設定**: サイドバーでGemini API Keyを入力
        2. **台本入力**: ファイルアップロードまたは直接入力
        3. **チェック実行**: 「チェック実行」ボタンをクリック
        4. **結果確認**: タブで分類された結果を確認
        5. **結果保存**: CSV またはテキスト形式でダウンロード
        
        **API Key取得:**
        [Google AI Studio](https://makersuite.google.com/app/apikey) でAPI Keyを取得してください。
        
        **対応ファイル:**
        現在はテキストファイル（.txt）のみサポートしています。
        """)

st.markdown("---")
st.markdown("💡 **ヒント**: API Keyなしでも基本的なチェック機能は利用できます。")

# 必要なライブラリ情報をコメントで追加
"""
必要なライブラリのインストール:
pip install streamlit google-generativeai pandas

実行方法:
streamlit run app.py
"""
