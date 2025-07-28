import streamlit as st
import re
import pandas as pd
from datetime import datetime
import io
import json
import time

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
    page_title="YouTube 2ch系動画制作 & 台本校正ツール",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #ff6b6b 0%, #4ecdc4 50%, #45b7d1 100%);
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
    
    .success-card {
        background-color: #e8f5e8;
        border-left-color: #27ae60;
    }
    
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem;
    }
    
    .genre-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem;
        cursor: pointer;
        transition: transform 0.3s;
    }
    
    .genre-card:hover {
        transform: translateY(-2px);
    }
    
    .mode-selector {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# メインタイトル
st.markdown('<h1 class="main-header">🎬 YouTube 2ch系動画制作 & 台本校正ツール</h1>', unsafe_allow_html=True)

class YouTubeScriptCreator:
    def __init__(self):
        self.genres = {
            "恋愛・人間関係": ["復讐劇", "恋愛トラブル", "三角関係", "不倫", "友情の破綻", "家族問題"],
            "職場・学校": ["ブラック企業", "パワハラ", "いじめ", "先輩後輩", "恋愛関係", "出世競争"],
            "復讐・因果応報": ["悪事の報い", "逆転劇", "復讐成功", "自業自得", "正義の勝利", "天罰"],
            "家族・親族": ["毒親", "遺産相続", "家族の秘密", "兄弟姉妹", "嫁姑問題", "離婚問題"],
            "金銭・詐欺": ["詐欺被害", "借金問題", "投資トラブル", "ギャンブル", "金の切れ目", "成金話"],
            "ホラー・オカルト": ["心霊体験", "都市伝説", "呪い", "怪談", "超常現象", "謎の体験"],
            "社会問題": ["ネット炎上", "SNSトラブル", "プライバシー", "格差社会", "時事問題", "世代論"],
            "日常・コメディ": ["勘違い", "失敗談", "珍事件", "おもしろ体験", "あるある", "ほっこり話"]
        }
        
        self.character_templates = {
            "主人公": ["投稿者", "A", "俺", "私", "僕"],
            "相手役": ["彼女", "彼氏", "友人", "B", "相手"],
            "敵役": ["上司", "先輩", "C", "DQN", "クレーマー"],
            "脇役": ["同僚", "友達", "D", "E", "通りすがり"],
            "ナレーション": ["N", "ナレ", "解説"]
        }
        
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
        ]

    def create_plot_from_genre(self, genre, sub_genre, mode, api_key, custom_settings=None):
        """ジャンルから新規プロット作成"""
        if not api_key or not GENAI_AVAILABLE:
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            if mode == "フルオート":
                prompt = f"""
                YouTube 2ch系動画のプロットを作成してください。
                
                ジャンル: {genre}
                サブジャンル: {sub_genre}
                
                以下の要素を含む、視聴者が最後まで見たくなるプロットを作成してください：
                
                1. キャッチーなタイトル
                2. 導入部（問題提起・状況設定）
                3. 展開部（対立・トラブル発生）
                4. クライマックス（対決・決着）
                5. 結末（因果応報・教訓）
                6. 主要キャラクター設定
                7. 推定視聴時間
                
                プロの作家レベルの完成度で、以下の特徴を意識してください：
                - 感情移入しやすいキャラクター
                - 予想外の展開
                - スカッとする結末
                - 道徳的な教訓
                - 視聴者の共感を呼ぶエピソード
                
                フォーマット：
                【タイトル】
                【概要】
                【キャラクター】
                【構成】
                【推定時間】
                """
            
            elif mode == "セミセルフ":
                settings_text = ""
                if custom_settings:
                    settings_text = f"""
                    追加設定：
                    - 主人公設定: {custom_settings.get('protagonist', '')}
                    - 相手役設定: {custom_settings.get('antagonist', '')}
                    - 舞台設定: {custom_settings.get('setting', '')}
                    - 特殊要素: {custom_settings.get('special', '')}
                    """
                
                prompt = f"""
                YouTube 2ch系動画のプロットを作成してください。
                
                ジャンル: {genre}
                サブジャンル: {sub_genre}
                {settings_text}
                
                ユーザーの設定を活かしつつ、プロレベルの完成度でプロットを作成してください。
                2ch系動画の特徴（リアリティ、共感性、スカッと感）を重視してください。
                
                フォーマット：
                【タイトル】
                【概要】
                【キャラクター】
                【構成】
                【推定時間】
                """
            
            else:  # セルフ
                return "セルフモードでは、ユーザーが独自にプロットを作成してください。"
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            st.error(f"プロット作成でエラーが発生しました: {str(e)}")
            return None

    def create_script_from_plot(self, plot_text, script_style, api_key):
        """プロットから台本作成"""
        if not api_key or not GENAI_AVAILABLE:
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            style_instructions = {
                "標準": "自然で読みやすい、一般的な2ch系動画スタイル",
                "ドラマチック": "感情豊かで演劇的、ドラマのような表現",
                "コメディ": "軽快でユーモラス、笑える要素を重視",
                "シリアス": "重厚で真面目、社会問題を扱うスタイル",
                "若者向け": "現代的でSNS世代向けの表現"
            }
            
            prompt = f"""
            以下のプロットを基に、YouTube 2ch系動画の完成台本を作成してください。
            
            【プロット】
            {plot_text}
            
            【スタイル】
            {style_instructions.get(script_style, '標準')}
            
            【台本作成指示】
            1. 各セリフの前に必ず話者名を明記してください（例：A「」、B「」、N「」）
            2. ナレーション部分は「N」で表記してください
            3. 視聴者が飽きない適度な長さ（15-20分程度）
            4. 感情の起伏を意識したセリフ構成
            5. 2ch系動画特有の臨場感とリアリティ
            6. 適所にツッコミや合いの手を入れる
            7. 視聴者の共感を呼ぶ表現
            
            プロの脚本家レベルの完成度で作成してください。
            
            フォーマット：
            【タイトル】
            【登場人物】
            【台本】
            """
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            st.error(f"台本作成でエラーが発生しました: {str(e)}")
            return None

    def enhance_script(self, script_text, enhancement_type, api_key):
        """台本の改善・調整"""
        if not api_key or not GENAI_AVAILABLE:
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            enhancement_prompts = {
                "感情表現強化": "感情表現をより豊かに、キャラクターの心情が伝わりやすく調整してください。",
                "テンポ改善": "会話のテンポを良くし、視聴者が飽きないリズムに調整してください。",
                "笑い要素追加": "適度なユーモアや笑える要素を追加して、エンターテイメント性を高めてください。",
                "リアリティ向上": "より現実的で共感しやすい表現に調整してください。",
                "スカッと感強化": "視聴者がスカッとする要素を強化し、カタルシスを高めてください。"
            }
            
            prompt = f"""
            以下の台本を改善してください。
            
            【改善目標】
            {enhancement_prompts.get(enhancement_type, '')}
            
            【現在の台本】
            {script_text}
            
            【改善指示】
            - 話者名の形式は維持してください
            - 元の構成や流れは保持してください
            - プロレベルの品質に仕上げてください
            - 2ch系動画の特徴を活かしてください
            
            改善後の台本を出力してください。
            """
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            st.error(f"台本改善でエラーが発生しました: {str(e)}")
            return None

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

            # 話者不明チェック
            line_stripped = line.strip()
            if line_stripped.startswith('「'):
                results.append({
                    'type': '話者不明',
                    'line': line_idx,
                    'position': 0,
                    'text': line,
                    'message': 'セリフの前にキャラクター名やナレーション(N)の指定がありません。',
                    'severity': 'suggestion'
                })
        
        return results

    def perform_ai_check(self, text, api_key):
        """Gemini AIを使用した高精度チェック"""
        if not GENAI_AVAILABLE or not api_key:
            return []
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            prompt = f"""以下の台本テキストを校正してください。誤字脱字、表記の統一、不自然な表現、台本として不適切な部分を指摘してください。
特に、各セリフの前に話者（キャラクター名やナレーション）が明確に指定されているかも確認し、話者が不明なセリフがあれば指摘してください。

【台本テキスト】
{text}

【指摘形式】
各指摘について以下の形式で回答してください：
- 種類: （誤字/脱字/表記統一/表現改善/話者不明/その他）
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
    
    # 機能選択
    st.subheader("🎯 機能選択")
    main_function = st.selectbox(
        "メイン機能",
        ["🎬 動画制作", "📝 台本校正"],
        help="メインで使用したい機能を選択してください"
    )

# メイン機能によって表示を切り替え
if main_function == "🎬 動画制作":
    # YouTube動画制作機能
    st.header("🎬 YouTube 2ch系動画制作")
    
    # ツール初期化
    creator = YouTubeScriptCreator()
    
    # 制作モード選択
    st.subheader("🎯 制作モード選択")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🤖 フルオート", help="AIが全自動で作成", use_container_width=True):
            st.session_state['creation_mode'] = 'フルオート'
    
    with col2:
        if st.button("🛠️ セミセルフ", help="設定入力後にAIが作成", use_container_width=True):
            st.session_state['creation_mode'] = 'セミセルフ'
    
    with col3:
        if st.button("✏️ セルフ", help="手動でプロット・台本作成", use_container_width=True):
            st.session_state['creation_mode'] = 'セルフ'
    
    # 選択されたモードに応じた処理
    if 'creation_mode' in st.session_state:
        mode = st.session_state['creation_mode']
        st.info(f"📌 選択モード: {mode}")
        
        # ジャンル選択
        st.subheader("🎭 ジャンル選択")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_genre = st.selectbox("メインジャンル", list(creator.genres.keys()))
        
        with col2:
            selected_subgenre = st.selectbox("サブジャンル", creator.genres[selected_genre])
        
        # モード別設定
        if mode == "セミセルフ":
            st.subheader("⚙️ 詳細設定")
            
            col1, col2 = st.columns(2)
            with col1:
                protagonist_setting = st.text_input("主人公設定", placeholder="例：20代会社員、内向的な性格")
                setting_place = st.text_input("舞台設定", placeholder="例：IT企業、学校、住宅街")
            
            with col2:
                antagonist_setting = st.text_input("相手役設定", placeholder="例：上司、同級生、隣人")
                special_element = st.text_input("特殊要素", placeholder="例：SNS、ペット、趣味")
            
            custom_settings = {
                'protagonist': protagonist_setting,
                'antagonist': antagonist_setting,
                'setting': setting_place,
                'special': special_element
            }
        else:
            custom_settings = None
        
        # プロット作成
        if mode != "セルフ":
            if st.button("📋 プロット作成", type="primary", use_container_width=True):
                if not api_key:
                    st.error("API Keyを入力してください")
                else:
                    with st.spinner("プロット作成中..."):
                        plot = creator.create_plot_from_genre(
                            selected_genre, selected_subgenre, mode, api_key, custom_settings
                        )
                        if plot:
                            st.session_state['created_plot'] = plot
                            st.success("プロット作成完了！")
        
        # プロット表示・編集
        if 'created_plot' in st.session_state or mode == "セルフ":
            st.subheader("📋 プロット")
            
            if mode == "セルフ":
                plot_text = st.text_area(
                    "プロットを入力してください",
                    height=300,
                    placeholder="ここにプロットを入力してください..."
                )
            else:
                plot_text = st.text_area(
                    "プロット（編集可能）",
                    value=st.session_state.get('created_plot', ''),
                    height=300
                )
            
            # 台本作成
            if plot_text.strip():
                st.subheader("🎬 台本作成")
                
                col1, col2 = st.columns(2)
                with col1:
                    script_style = st.selectbox(
                        "台本スタイル",
                        ["標準", "ドラマチック", "コメディ", "シリアス", "若者向け"]
                    )
                
                with col2:
                    if st.button("📝 台本作成", type="primary"):
                        if not api_key:
                            st.error("API Keyを入力してください")
                        else:
                            with st.spinner("台本作成中..."):
                                script = creator.create_script_from_plot(plot_text, script_style, api_key)
                                if script:
                                    st.session_state['created_script'] = script
                                    st.success("台本作成完了！")

# 台本表示・編集エリア
if 'created_script' in st.session_state:
    st.subheader("📝 作成された台本")
    
    script_text = st.text_area(
        "台本（編集可能）",
        value=st.session_state['created_script'],
        height=400
    )
    
    # 台本改善機能
    st.subheader("🔧 台本改善")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("😊 感情表現強化"):
            if api_key:
                with st.spinner("改善中..."):
                    enhanced = creator.enhance_script(script_text, "感情表現強化", api_key)
                    if enhanced:
                        st.session_state['created_script'] = enhanced
                        st.rerun()
    
    with col2:
        if st.button("⚡ テンポ改善"):
            if api_key:
                with st.spinner("改善中..."):
                    enhanced = creator.enhance_script(script_text, "テンポ改善", api_key)
                    if enhanced:
                        st.session_state['created_script'] = enhanced
                        st.rerun()
    
    with col3:
        if st.button("😄 笑い要素追加"):
            if api_key:
                with st.spinner("改善中..."):
                    enhanced = creator.enhance_script(script_text, "笑い要素追加", api_key)
                    if enhanced:
                        st.session_state['created_script'] = enhanced
                        st.rerun()
    
    # 台本ダウンロード
    st.subheader("💾 台本保存")
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📄 台本をダウンロード",
            data=script_text,
            file_name=f"youtube_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    
    with col2:
        if st.button("📝 校正機能で確認"):
            st.session_state['script_for_proofreading'] = script_text
            st.session_state['main_function'] = "📝 台本校正"
            st.rerun()

elif main_function == "📝 台本校正":
    # 台本校正機能（既存の機能）
    st.header("📝 台本校正機能")
    
    # ツール初期化
    creator = YouTubeScriptCreator()
    
    # ファイルアップロード
    with st.sidebar:
        st.subheader("📁 ファイル読み込み")
        uploaded_file = st.file_uploader(
            "📁 ファイルをアップロード",
            type=['txt'],
            help="テキストファイルをアップロードできます"
        )
        
        # チェックオプション
        st.subheader("チェックオプション")
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
        
        # 制作機能からの台本がある場合
        if 'script_for_proofreading' in st.session_state:
            script_text = st.session_state['script_for_proofreading']
            st.info("🎬 動画制作機能から台本が読み込まれました")
            del st.session_state['script_for_proofreading']  # 一度使ったら削除
        
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
                all_results = []
                
                with st.spinner("チェック中..."):
                    # 基本チェック
                    if use_basic_check:
                        basic_results = creator.perform_basic_check(script_input)
                        all_results.extend(basic_results)
                    
                    # AIチェック
                    if use_ai_check and api_key and GENAI_AVAILABLE:
                        ai_results = creator.perform_ai_check(script_input, api_key)
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
    tab1, tab2, tab3 = st.tabs(["🎬 動画制作機能", "📝 校正機能", "🔧 使い方"])
    
    with tab1:
        st.markdown("""
        ### 🎬 YouTube 2ch系動画制作機能
        
        **制作モード:**
        - **フルオート**: AIが完全自動で高品質なプロット・台本を作成
        - **セミセルフ**: ユーザーが設定を入力し、AIが創作をサポート
        - **セルフ**: ユーザーが手動でプロット・台本を作成
        
        **対応ジャンル:**
        - 恋愛・人間関係（復讐劇、恋愛トラブル、三角関係など）
        - 職場・学校（ブラック企業、パワハラ、いじめなど）
        - 復讐・因果応報（悪事の報い、逆転劇、復讐成功など）
        - 家族・親族（毒親、遺産相続、家族の秘密など）
        - 金銭・詐欺（詐欺被害、借金問題、投資トラブルなど）
        - ホラー・オカルト（心霊体験、都市伝説、呪いなど）
        - 社会問題（ネット炎上、SNSトラブル、格差社会など）
        - 日常・コメディ（勘違い、失敗談、珍事件など）
        
        **台本スタイル:**
        - 標準、ドラマチック、コメディ、シリアス、若者向け
        
        **改善機能:**
        - 感情表現強化、テンポ改善、笑い要素追加、リアリティ向上、スカッと感強化
        """)
    
    with tab2:
        st.markdown("""
        ### 📝 台本校正機能
        
        **基本チェック機能:**
        - 句読点・感嘆符の重複検出
        - 空白の重複チェック
        - 全角英数字の検出
        - 表記統一チェック（「出来る」→「できる」等）
        - 行の長さチェック
        - セリフの形式チェック
        - **話者が不明なセリフの検出**
        
        **AI機能（Gemini 1.5 Flash）:**
        - 高精度な誤字脱字検出
        - 表記統一の提案
        - 不自然な表現の指摘
        - **話者が不明なセリフの指摘**
        - 台本として適切な修正提案
        
        **エクスポート機能:**
        - CSV形式での結果出力
        - テキスト形式での結果出力
        - 台本ファイルのダウンロード
        """)
    
    with tab3:
        st.markdown("""
        ### 🔧 使い方ガイド
        
        **🎬 動画制作の場合:**
        1. **API設定**: サイドバーでGemini API Keyを入力
        2. **機能選択**: 「🎬 動画制作」を選択
        3. **モード選択**: フルオート/セミセルフ/セルフから選択
        4. **ジャンル選択**: メインジャンルとサブジャンルを選択
        5. **設定入力**: セミセルフの場合は詳細設定を入力
        6. **プロット作成**: AIによるプロット生成または手動入力
        7. **台本作成**: スタイルを選択してAIが台本を生成
        8. **改善・調整**: 感情表現やテンポなどを改善
        9. **保存**: 完成した台本をダウンロード
        
        **📝 校正の場合:**
        1. **API設定**: サイドバーでGemini API Keyを入力
        2. **機能選択**: 「📝 台本校正」を選択
        3. **台本入力**: ファイルアップロードまたは直接入力
        4. **チェック実行**: 基本チェック・AIチェックを実行
        5. **結果確認**: タブで分類された結果を確認
        6. **結果保存**: CSV またはテキスト形式でダウンロード
        
        **API Key取得:**
        [Google AI Studio](https://makersuite.google.com/app/apikey) でAPI Keyを取得してください。
        
        **プロレベルの品質:**
        - 視聴者が最後まで見たくなる構成
        - 感情移入しやすいキャラクター設定
        - 予想外の展開とスカッとする結末
        - 2ch系動画特有のリアリティと臨場感
        - 適切な話者表記と読みやすい台本形式
        """)

st.markdown("---")
st.markdown("💡 **ヒント**: API Keyなしでも基本的なチェック機能は利用できます。プロレベルの動画制作にはAPI Keyが必要です。")

# 必要なライブラリ情報をコメントで追加
"""
必要なライブラリのインストール:
pip install streamlit google-generativeai pandas regex

実行方法:
streamlit run youtube_script_creator.py

機能一覧:
1. YouTube 2ch系動画のプロット・台本自動生成
2. フルオート/セミセルフ/セルフの3つの制作モード
3. 8つのジャンル×各6サブジャンル対応
4. 5つの台本スタイル（標準/ドラマチック/コメディ/シリアス/若者向け）
5. 台本改善機能（感情表現強化/テンポ改善/笑い要素追加等）
6. 高精度誤字脱字チェック機能
7. 話者不明セリフの自動検出
8. プロレベルの品質保証
"""basic_check = st.checkbox("基本チェック", value=True)
        use_
