"""日本語 / 한국어 界面文字，以及所有语言新增的条目（日服/韩服、识别模型下载）。"""

# 所有语言都要有的新条目
EXTRA = {
    "zh": {
        "srv_jp": "日服", "srv_kr": "韩服",
        "data_info": "国服 {cn} · 国际服 {en} · 日服 {jp} · 韩服 {kr} 人 · 上次检查 {t}",
        "dl_model": "正在下载{lang}识别模型（约 {mb}MB，仅一次）…",
        "dl_done": "{lang}识别模型已就绪", "dl_fail": "{lang}识别模型下载失败：{e}",
        "lang_ja": "日语", "lang_ko": "韩语",
    },
    "en": {
        "srv_jp": "JP", "srv_kr": "KR",
        "data_info": "CN {cn} · Global {en} · JP {jp} · KR {kr} · checked {t}",
        "dl_model": "Downloading {lang} text model (~{mb} MB, one time)…",
        "dl_done": "{lang} text model ready", "dl_fail": "{lang} text model download failed: {e}",
        "lang_ja": "Japanese", "lang_ko": "Korean",
    },
}

JA = {
    "app": "公開求人アシスタント", "panel_title": "公開求人 · 分析",
    "pick": "クリックで自動選択 ›", "pick_hint": "組み合わせをクリック → タグと時間を自動設定",
    "need_admin": "⚠ ゲームが管理者権限で動いています。自動選択にはこのツールも管理者権限が必要です — クリックで再起動",
    "applying": "タグを選択しています…", "applied": "選択済み：{tags}  ·  {time}",
    "apply_fail": "自動選択が完了しませんでした。ゲーム内のタグと時間を確認してください",
    "apply_stopped": "自動選択を中止しました：マウスが動いたかウィンドウが切り替わりました（安全のため）",
    "v_six": "上級エリート", "v_six_s": "「上級エリート」を選んで 9 時間 → ★6 確定",
    "v_five": "★5 確定", "v_five_s": "{tags}",
    "v_four": "★4 確定", "v_four_s": "{tags}",
    "v_robot": "ロボット", "v_robot_s": "「ロボット」だけを選んで 3:50 → ★1 ロボット確定",
    "v_three": "★3 のみ", "v_three_s": "タグを更新するか、そのまま 9 時間で",
    "empty3": "★4 以上が確定する組み合わせはありません。",
    "wait_game": "ゲームの起動を待っています…", "wait_recruit": "公開求人のタグ選択画面を開いてください",
    "game_on": "ゲーム接続中", "game_off": "ゲームが見つかりません", "admin_on": "管理者", "admin_off": "管理者ではない",
    "manual": "タグを手動で選ぶ", "settings": "設定", "scan": "認識 (F8)",
    "loading_ocr": "OCR を読み込み中…", "scan_none": "公開求人のタグが見つかりません",
    "found": "タグ {n} 個 · {srv} · {t:.1f}s",
    "srv_cn": "中国版", "srv_en": "グローバル版", "srv_jp": "日本版", "srv_kr": "韓国版",
    "s_lang": "表示言語", "s_server": "サーバー", "s_auto": "自動",
    "s_display": "表示", "s_overlay": "ゲーム内オーバーレイ (F9)", "s_watch": "自動認識", "s_show3": "★3 の組み合わせも表示",
    "s_start": "起動方法", "st_manual": "手動で開く", "st_logon": "バックグラウンドで待機（おすすめ）",
    "st_with_game": "ゲームと一緒に起動（デスクトップショートカット）",
    "st_desc": "バックグラウンド待機：ログイン後トレイで静かに待ち、ゲームを開くと自動で動きます。負荷はほぼゼロです。\n"
               "ゲームと一緒に起動：新しいショートカットでゲームとこのツールを同時に起動し、ゲーム終了時に閉じます。",
    "s_on_exit": "ゲーム終了時", "ex_quit": "ツールを終了", "ex_stay": "待機を続ける",
    "s_area": "認識範囲", "area_auto": "自動（ゲームウィンドウ）", "area_pick": "範囲を選択（エミュレーター）",
    "s_data": "オペレーターデータ", "data_update": "今すぐ更新",
    "data_info": "中国版 {cn} · グローバル {en} · 日本版 {jp} · 韓国版 {kr} · 最終確認 {t}",
    "s_launcher": "Hypergryph ランチャー", "browse": "参照…",
    "s_remove": "自動起動とショートカットを削除",
    "need_admin_short": "⚠ 自動選択には管理者権限が必要（クリック）", "card_label": "おすすめ",
    "ops_more": "ほか {n} 名", "more_combos": "あと {n} 件",
    "s_style": "結果の表示", "style_card": "公開求人画面に埋め込む", "style_panel": "サイドパネル",
    "s_update": "データ更新のタイミング", "up_game": "ゲーム起動時", "up_6h": "6 時間ごと", "up_manual": "手動のみ",
    "region_tip": "ドラッグしてゲーム画面（エミュレーター）を選択、Esc でキャンセル",
    "updating": "データを更新中…", "updated": "データを更新しました", "uptodate": "データは最新です",
    "update_fail": "更新に失敗しました：{e}",
    "applied_startup": "起動方法を保存しました", "startup_fail": "起動方法の設定に失敗しました（管理者権限が必要）",
    "t_show": "メイン画面を開く", "t_overlay": "オーバーレイ", "t_quit": "完全に終了（次回ログインまで）",
    "t_sleep": "閉じる（次にゲームを開くと自動で戻ります）",
    "w_title": "公開求人アシスタントへようこそ",
    "w_sub": "公開求人の画面を開くと、選ぶべきタグをゲーム画面上に直接表示します。",
    "w_shortcut": "デスクトップにショートカットを作成", "w_go": "はじめる",
    "w_admin": "完了時に一度だけ管理者権限を求めます（自動起動と自動選択のため）。以後は聞かれません。",
    "hotkeys": "F8 すぐに認識 · F9 オーバーレイの表示/非表示",
    "w_steps": "①  ゲームで「公開求人」を開き、空いている募集枠をタップ\n"
               "②  画面の横に「おすすめ」が出て、良いオペレーターが出るか教えてくれます\n"
               "③  おすすめをクリックすると、タグと時間を自動で設定。あとは確定を押すだけ",
    "w_install": "インストールしてはじめる", "w_start": "はじめる", "w_installing": "インストール中、お待ちください…",
    "w_more": "その他のオプション", "w_auto": "これからは Windows と一緒に静かに起動します。他に操作は不要です。",
    "u_btn": "アンインストール",
    "u_confirm": "公開求人アシスタントをアンインストールしますか？\nプログラム、設定、ショートカットがすべて削除されます。",
    "dl_model": "{lang}の文字認識モデルをダウンロード中（約 {mb}MB、初回のみ）…",
    "dl_done": "{lang}の文字認識モデルの準備ができました", "dl_fail": "{lang}の文字認識モデルのダウンロードに失敗：{e}",
    "lang_ja": "日本語", "lang_ko": "韓国語",
}

KO = {
    "app": "공개모집 도우미", "panel_title": "공개모집 · 분석",
    "pick": "클릭하여 자동 선택 ›", "pick_hint": "조합을 클릭 → 태그와 시간이 자동으로 설정됩니다",
    "need_admin": "⚠ 게임이 관리자 권한으로 실행 중입니다. 자동 선택하려면 이 도구도 관리자 권한이 필요합니다 — 클릭하여 다시 시작",
    "applying": "태그를 선택하는 중…", "applied": "선택 완료: {tags}  ·  {time}",
    "apply_fail": "자동 선택이 완료되지 않았습니다. 게임에서 태그와 시간을 확인하세요",
    "apply_stopped": "자동 선택 중지: 마우스를 움직였거나 창을 전환했습니다 (안전 보호)",
    "v_six": "고급 특별 채용", "v_six_s": "「고급 특별 채용」 선택, 9시간 → 6성 확정",
    "v_five": "5성 확정", "v_five_s": "{tags}",
    "v_four": "4성 확정", "v_four_s": "{tags}",
    "v_robot": "로봇", "v_robot_s": "「로봇」만 선택하고 3:50 → 1성 로봇 확정",
    "v_three": "3성만 가능", "v_three_s": "태그를 새로고침하거나 그냥 9시간으로",
    "empty3": "4성 이상이 확정되는 조합이 없습니다.",
    "wait_game": "게임 실행을 기다리는 중…", "wait_recruit": "공개모집 태그 선택 화면을 열어 주세요",
    "game_on": "게임 연결됨", "game_off": "게임을 찾을 수 없음", "admin_on": "관리자", "admin_off": "관리자 아님",
    "manual": "태그 직접 선택", "settings": "설정", "scan": "인식 (F8)",
    "loading_ocr": "OCR 불러오는 중…", "scan_none": "공개모집 태그를 찾지 못했습니다",
    "found": "태그 {n}개 · {srv} · {t:.1f}s",
    "srv_cn": "중국 서버", "srv_en": "글로벌", "srv_jp": "일본 서버", "srv_kr": "한국 서버",
    "s_lang": "표시 언어", "s_server": "서버", "s_auto": "자동",
    "s_display": "표시", "s_overlay": "게임 내 오버레이 (F9)", "s_watch": "자동 인식", "s_show3": "3성 조합도 표시",
    "s_start": "시작 방식", "st_manual": "직접 열기", "st_logon": "백그라운드 대기 (추천)",
    "st_with_game": "게임과 함께 시작 (바탕화면 바로가기)",
    "st_desc": "백그라운드 대기: 로그인 후 트레이에서 조용히 기다리다가 게임을 열면 자동으로 작동합니다. 부하는 거의 없습니다.\n"
               "게임과 함께 시작: 새 바로가기로 게임과 이 도구를 함께 실행하고, 게임을 닫으면 같이 종료됩니다.",
    "s_on_exit": "게임 종료 시", "ex_quit": "도구 종료", "ex_stay": "계속 대기",
    "s_area": "인식 범위", "area_auto": "자동 (게임 창)", "area_pick": "범위 선택 (에뮬레이터)",
    "s_data": "오퍼레이터 데이터", "data_update": "지금 업데이트",
    "data_info": "중국 {cn} · 글로벌 {en} · 일본 {jp} · 한국 {kr} · 마지막 확인 {t}",
    "s_launcher": "Hypergryph 런처", "browse": "찾아보기…",
    "s_remove": "자동 시작과 바로가기 삭제",
    "need_admin_short": "⚠ 자동 선택은 관리자 권한 필요 (클릭)", "card_label": "추천",
    "ops_more": "외 {n}명", "more_combos": "{n}개 더 보기",
    "s_style": "결과 표시", "style_card": "공개모집 화면에 표시", "style_panel": "사이드 패널",
    "s_update": "데이터 업데이트 시점", "up_game": "게임 시작 시", "up_6h": "6시간마다", "up_manual": "수동만",
    "region_tip": "드래그하여 게임 화면(에뮬레이터)을 선택, Esc로 취소",
    "updating": "데이터 업데이트 중…", "updated": "데이터를 업데이트했습니다", "uptodate": "데이터가 최신입니다",
    "update_fail": "업데이트 실패: {e}",
    "applied_startup": "시작 방식을 저장했습니다", "startup_fail": "시작 방식 설정 실패 (관리자 권한 필요)",
    "t_show": "메인 창 열기", "t_overlay": "오버레이", "t_quit": "완전히 종료 (다음 로그인까지)",
    "t_sleep": "닫기 (다음에 게임을 열면 자동으로 돌아옵니다)",
    "w_title": "공개모집 도우미에 오신 것을 환영합니다",
    "w_sub": "공개모집 화면을 열면 골라야 할 태그를 게임 화면 위에 바로 표시합니다.",
    "w_shortcut": "바탕화면에 바로가기 만들기", "w_go": "시작하기",
    "w_admin": "완료할 때 관리자 권한을 한 번만 요청합니다 (자동 시작과 자동 선택용). 이후에는 묻지 않습니다.",
    "hotkeys": "F8 바로 인식 · F9 오버레이 표시/숨기기",
    "w_steps": "①  게임에서 「공개모집」을 열고 빈 모집 칸을 누르세요\n"
               "②  화면 옆에 「추천」이 나타나 좋은 오퍼레이터가 나올 수 있는지 알려줍니다\n"
               "③  추천을 클릭하면 태그와 시간이 자동으로 설정됩니다. 확인만 누르세요",
    "w_install": "설치하고 시작하기", "w_start": "시작하기", "w_installing": "설치 중입니다. 잠시만 기다려 주세요…",
    "w_more": "추가 옵션", "w_auto": "이제부터 Windows와 함께 조용히 시작됩니다. 따로 할 일은 없습니다.",
    "u_btn": "제거",
    "u_confirm": "공개모집 도우미를 제거할까요?\n프로그램, 설정, 바로가기가 모두 삭제됩니다.",
    "dl_model": "{lang} 문자 인식 모델 다운로드 중 (약 {mb}MB, 한 번만)…",
    "dl_done": "{lang} 문자 인식 모델 준비 완료", "dl_fail": "{lang} 문자 인식 모델 다운로드 실패: {e}",
    "lang_ja": "일본어", "lang_ko": "한국어",
}


def install(text: dict):
    """把日韩文字和新增条目合并进 app.TEXT"""
    for lang, extra in EXTRA.items():
        text[lang].update(extra)
    text["ja"] = JA
    text["ko"] = KO
    missing = {lang: sorted(set(text["en"]) - set(text[lang])) for lang in ("zh", "ja", "ko")}
    assert not any(missing.values()), f"untranslated keys: {missing}"
