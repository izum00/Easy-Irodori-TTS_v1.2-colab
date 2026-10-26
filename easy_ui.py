"""Japanese guided UI using the unchanged upstream synthesis functions."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import traceback

import gradio as gr
import easy_dictionary
import easy_options as opt
import easy_memory as mem
from easy_audio import change_speed, VOLUME_HTML, VOLUME_JS
from easy_text_tools import build_dictionary_tab, build_emoji_picker, preview

ROOT = Path(__file__).resolve().parent
MODELS = [("ベース（標準モデル）", "Aratako/Irodori-TTS-v4.1-Small"),
          ("Anime（派生版のアニメ声強化モデル）", "phasefield-audio/Irodori-TTS-v4.1-Anime"), ("MF（標準モデルの高速版）", opt.MF)]
MODES = [("言葉で声を作る（ボイスデザイン）", "design"),
         ("お手本の声に似せる（ボイスクローン）", "clone"),
         ("お手本の声＋話し方を指定", "both"), ("文章だけでおまかせ", "auto")]
CSS = """
.gradio-container {max-width: 1080px !important; margin: auto;}
#easy-hero {padding: 22px; border-radius: 16px; background: linear-gradient(120deg,#eaf5f1,#eef2ff); color: var(--body-text-color);}
#easy-hero, #easy-hero * {color: var(--body-text-color) !important;}
.easy-emoji {padding: 7px 10px; border: 1px solid #80808066; border-radius: 8px; background: transparent; color: inherit; cursor: pointer;} .easy-emoji:hover, .easy-emoji:focus-visible {background: #6688aa33;} .easy-step {margin-top: 20px !important;}
footer {display: none !important;}
"""


def footer_text():
    config = ROOT / "config" / "credits.json"
    author = ""
    if config.exists():
        data = json.loads(config.read_text(encoding="utf-8-sig"))
        author = str(data.get("author", "")).strip()
    credit = f"Easy-Irodori-TTS 制作：{author} (https://www.youtube.com/@yuupro) with Codex  \n" if author else ""
    return credit + """音声合成エンジン・ベースモデル：**[Aratako](https://github.com/Aratako/Irodori-TTS)**  
Animeモデル：**[phasefield-audio](https://huggingface.co/phasefield-audio/Irodori-TTS-v4.1-Anime)**  
MFモデル：**[Aratako / Irodori-TTS-v4.1-Small-MF](https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small-MF)**  

### ライセンス: [MIT License](https://licenses.opensource.jp/MIT/MIT.html)

### 禁止事項・免責事項
- **本人の同意なしに声を複製して公開したり、なりすまし等の悪用はしないでください。**
- **人をだます目的での使用や誤情報の拡散等に使用するのも厳禁です。**
- 参照音声を使わない場合であっても、偶然実在の人物に似た音声となる可能性があります。
- 生成物の利用は、利用者の責任で適用される法令・規則に従ってください。
- ユーザーは生成音声の使用に関するリスクと責任を負うものとします。
- 本ノートブックは「現状のまま」提供され、開発者は一切の責任を負いません

上記のほかにも
[ベースモデルの利用条件](https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small#license--ethical-restrictions)・
[Animeモデルの利用条件](https://huggingface.co/phasefield-audio/Irodori-TTS-v4.1-Anime#license)をご確認ください。
"""


def mode_visibility(mode):
    return gr.update(visible=mode in ("clone", "both")), gr.update(visible=mode in ("design", "both"))


def error_message(exc):
    message = str(exc).lower()
    if "out of memory" in message:
        return "GPUメモリが不足しました。候補数や文章の長さを減らすか、「モデルをメモリから解放」を押してから再度お試しください。"
    if any(word in message for word in ("connection", "download", "offline", "timeout")):
        return "モデルの取得または通信でエラーが発生しました。インターネット接続を確認して再度お試しください。"
    if isinstance(exc, ValueError):
        return "入力値を確認してください。数値欄には数値を入力し、任意の項目は空欄にできます。"
    return "生成できませんでした。入力や設定を確認してください。原因は下の「実行記録」で確認できます。"


def generation_handler(upstream, keys):
    count = upstream.MAX_GRADIO_CANDIDATES

    def empty(status, detail=""):
        return ([gr.update(value=None, visible=(i == 0)) for i in range(count)]
                + [gr.update(value=None, visible=False) for _ in range(count)] + [status, detail])

    def generate(mode, dictionary_enabled, speed, *values, progress=gr.Progress()):
        params = dict(zip(keys, values))
        if not str(params["text"] or "").strip():
            yield empty("文章が空欄です。文章欄に読み上げたい文章を入力してください。")
            return
        if mode in ("clone", "both") and not params["ref_wavs"]:
            yield empty("お手本の音声がありません。声の設定に音声ファイルを追加してください。")
            return
        if mode not in ("clone", "both"):
            params["ref_wavs"] = None
        if mode not in ("design", "both"):
            params["caption"] = ""
        yield empty("生成しています。初回はモデルを取得するため時間がかかります。画面を閉じずにお待ちください。")
        progress(0, desc="モデルの準備・音声生成中")
        mem.release()  # 前回の生成で残ったRAM・GPUキャッシュを先に解放
        ram_before = mem.process_gb()
        try:
            original_text=params['text']
            saved_settings=opt.read()
            saved_settings['_generation_date']=__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
            # Generated files belong exclusively to v1.2's internal directory.
            # The launcher sets cwd here, so upstream relative outputs remain contained.
            if params['checkpoint']==opt.MF:
                params.update(cfg_scale_text=0,cfg_scale_caption=0,cfg_scale_speaker=0,cfg_guidance_mode='independent',t_schedule_mode='linear',sway_coeff=0,cfg_scale_raw='',speaker_kv_scale_raw='',truncation_factor_raw='',rescale_k_raw='',rescale_sigma_raw='')
            current_key=(params['checkpoint'],params['model_device'],params['codec_device'],params['model_precision'],params['codec_precision'])
            if getattr(upstream,'_easy_last_key',None)!=current_key:
                upstream._clear_runtime_cache();upstream._easy_last_key=current_key
            params["text"] = easy_dictionary.apply(params["text"], dictionary_enabled)
            result = upstream._run_generation(**params)
            audios = list(result[:count])
            speed_paths = []
            for item in audios:
                if item.get("value"):
                    item["value"] = change_speed(item["value"], speed)
                    speed_paths.append(str(item["value"]))
            speed_paths,export_note=opt.export(speed_paths,saved_settings,original_text)
            for item,path in zip([a for a in audios if a.get('value')],speed_paths):item['value']=path
            result = list(result)
            result.append("話速: " + str(speed) + "倍\n保存先:\n" + "\n".join(speed_paths))
            downloads = [gr.update(value=item.get("value"), visible=bool(item.get("value"))) for item in audios]
            if saved_settings.get('unload_after'):
                upstream._clear_runtime_cache();upstream._easy_last_key=None
            mem.release()  # 生成が終わったらRAM・GPUキャッシュを解放
            memory_note = mem.summary(ram_before)
            result.append(memory_note)
            progress(1, desc="生成完了")
            yield audios + downloads + ["生成が完了しました。音声は「WAVをダウンロード」で保存もできます。\n"+export_note+"\n"+memory_note, "\n\n".join(result[count:])]
        except Exception as exc:
            traceback.print_exc()
            detail = traceback.format_exc()
            message = error_message(exc)
            exc = None
            mem.release()  # エラー後もRAM・GPUキャッシュを解放
            yield empty(message, detail)
    return generate


# Desktop layout: 16:9 monitor, with room for browser chrome.
CSS += """
.gradio-container {width:min(1880px, calc((100dvh - 20px) * 16 / 9)) !important; max-width:98vw !important; padding:10px !important; margin:auto !important;}
#easy-hero {padding:10px 18px !important; border-radius:12px;}
#easy-hero h1 {font-size:24px !important; margin:0 0 3px !important;}
#easy-hero p {margin:0 !important; font-size:13px !important;}
#workspace-row {gap:16px !important; align-items:stretch;}
.work-panel {height:auto; min-height:0; padding:14px !important; border:1px solid #8899aa44; border-radius:14px; gap:10px !important;}
.work-panel h3 {font-size:17px !important; margin:0 !important;}
.work-panel p {font-size:12px !important; margin:2px 0 !important;}
.work-panel label, .work-panel span {font-size:13px;}
#emoji-area .easy-emoji {font-size:13px; padding:7px 8px;}
#emoji-area section {margin:0;}
#emoji-area h4 {display:none;}
#dictionary-wide {display:grid !important; grid-template-columns:1fr 1fr; gap:10px 24px !important; align-content:start;}
#dictionary-wide > :first-child, #dictionary-wide > :last-child {grid-column:1/-1;}
#dictionary-wide .prose h2 {font-size:20px; margin:0;}
#dictionary-wide .prose p {margin:3px 0; font-size:13px;}
#dictionary-wide .table-wrap {max-height:200px;}
.settings-page {gap:14px; padding:12px;}
#credits-page {padding:12px 22px; font-size:14px;}
#credits-page h3 {font-size:18px; margin:12px 0 5px;}
@media (max-width:1250px), (max-height:790px) {
 .gradio-container {width:98vw !important;}
 .work-panel {height:auto; min-height:0;}
}
"""


def compact_generation(upstream, keys):
    original = generation_handler(upstream, keys)
    count = upstream.MAX_GRADIO_CANDIDATES
    def generate(mode, enabled, speed, *values, progress=gr.Progress()):
        for result in original(mode, enabled, speed, *values, progress=progress):
            paths = [item.get("value") for item in result[:count] if item.get("value")]
            choices = [(f"音声 {i + 1}", str(i)) for i in range(len(paths))]
            first = paths[0] if paths else None
            yield (first, gr.update(value=first, visible=bool(first)),
                   gr.update(choices=choices, value="0" if paths else None),
                   paths, result[-2], result[-1])
    return generate


def build_ui(upstream):
    from easy_text_tools import grouped_emojis
    from irodori_tts.gradio_emoji_palette import EMOJI_PALETTE_ITEMS
    device = upstream._default_model_device()
    devices = upstream.list_available_runtime_devices()
    devices = [d for d in devices if d in ('cpu',device)]
    precisions = upstream._precision_choices_for_device(device)
    controls = {}
    with gr.Blocks(title="Easy_Irodori_TTS v1.2 (Colab)") as demo:
        gr.Markdown("# Easy-Irodori-TTS-v1.2 (Google Colab版)\nこのアプリは、Aratako様が開発されたIrodori-TTSを初心者向けに使いやすくしたものです。標準・Anime・MF（高速）を切り替えて使用できます。", elem_id="easy-hero")
        with gr.Tabs():
            with gr.Tab("音声作成",render_children=True):
                with gr.Row(elem_id="workspace-row"):
                    with gr.Column(scale=3, min_width=300, elem_classes="work-panel"):
                        gr.Markdown("### ① モデル・声を選ぶ")
                        controls["checkpoint"] = gr.Dropdown(MODELS, value=MODELS[0][1], label="使うモデル", info="ベースは標準、Animeはアニメ調の派生モデルです。")
                        mode = gr.Dropdown(MODES, value="design", label="声の作り方")
                        with gr.Column(visible=False) as reference_group:
                            controls["ref_wavs"] = gr.File(label="お手本の音声", type="filepath", file_count="multiple", file_types=["audio"], allow_reordering=True, height=100)
                            gr.Markdown("自分の声、または本人の同意を得た声を使用してください。")
                        with gr.Column() as caption_group:
                            controls["caption"] = gr.Textbox(label="声・話し方の説明", lines=3, max_lines=3, placeholder="落ち着いた女性の声で、やわらかく丁寧に話す。", info="声の高さ・雰囲気・感情を短く指定します。")
                            preset = gr.Dropdown(["落ち着いた女性の声で、やわらかく丁寧に話す。", "明るく元気な声で、楽しそうに話す女性。", "低めの男性の声で、ゆっくり穏やかに話す。"], label="説明の入力例", value=None)
                            preset.input(lambda value: value or "", preset, controls["caption"], queue=False)
                        mode.change(mode_visibility, mode, [reference_group, caption_group], queue=False)
                        dictionary_enabled = gr.Checkbox(value=True, label="読み辞書を使う")
                        gr.Markdown("読み方の登録は「読み辞書」タブ。細かな調整は、このタブ下部の「生成設定」「詳細設定」を開いて行えます。")
                    with gr.Column(scale=5, min_width=450, elem_classes="work-panel"):
                        gr.Markdown("### ② 文章・絵文字を入力")
                        controls["text"] = gr.Textbox(label="読み上げる文章", lines=6, max_lines=6, placeholder="どうもおばんでした。今日はどんな一日でしたか？", info="読み間違える漢字や名前は、読み辞書で登録できます。", elem_id="irodori-voicedesign-text-input")
                        gr.Markdown("挿入したい場所をクリックしてから絵文字を選んでください。選択中の文字は置き換えます。")
                        with gr.Tabs(elem_id="emoji-area"):
                            for title, items in grouped_emojis(EMOJI_PALETTE_ITEMS):
                                with gr.Tab(title,render_children=True):
                                    build_emoji_picker(items=items, show_help=False)
                        preview_button = gr.Button("読み辞書を反映した文章を確認")
                        preview_text = gr.Textbox(label="読み上げに使う文章（確認用）", interactive=False, lines=3, max_lines=3)
                        preview_button.click(preview, [controls["text"], dictionary_enabled], preview_text)
                    with gr.Column(scale=3, min_width=300, elem_classes="work-panel"):
                        gr.Markdown("### ③ 音声を生成・保存")
                        generate = gr.Button("音声を生成する", variant="primary", size="lg", elem_id="easy-generate-button")
                        status = gr.Textbox(value="文章を入力して生成ボタンを押してください。", label="現在の状態", interactive=False, lines=3, max_lines=3)
                        selected_audio = gr.Dropdown([], label="聞き比べる音声", info="複数候補を作った場合、ここで切り替えられます。")
                        audio = gr.Audio(label="できあがった音声", type="filepath", interactive=False, buttons=["download"], elem_id="easy-generated-audio")
                        gr.HTML(VOLUME_HTML)
                        download = gr.DownloadButton(label="WAVをダウンロード", visible=False)
                        paths = gr.State([])
                        gr.Markdown("初回はモデルの取得に時間がかかります。自動保存の有無と保存先は「オプション設定」で変更できます。")
                # Mount controls before restoring values; Gradio 6 lazy accordion updates can hide them.
                with gr.Accordion("生成設定", open=True) as generation_settings:
                    with gr.Row(elem_classes="settings-page"):
                        with gr.Column():
                            controls["num_steps"] = gr.Slider(1,120,value=40,step=1,label="生成の計算回数",info="多いほど時間がかかります。最初は40で試してください。")
                            controls["num_candidates"] = gr.Slider(1,upstream.MAX_GRADIO_CANDIDATES,value=1,step=1,label="生成する候補数",info="複数の声を作って聞き比べます。生成結果の選択欄で切り替えます。")
                            speed = gr.Slider(0.75,1.5,value=1,step=0.05,label="話速（倍）",info="1.00が標準。声の高さを保って速度を変更し、WAVにも反映します。自然さを保つ目安は0.85～1.20です。変更後は再生成してください。")
                            controls["duration_scale"] = gr.Slider(0.5,1.5,value=1,step=0.01,label="生成する長さの倍率",info="1が標準。大きいほど長めに生成します。")
                        with gr.Column():
                            controls["seed_raw"] = gr.Textbox(label="再現用の番号（シード）",info="空欄なら毎回ランダムです。")
                            controls["seconds_raw"] = gr.Textbox(label="生成する秒数（任意）",info="通常は空欄で自動推定します。")
                            for name,label,value in [("cfg_scale_text","文章への忠実さ",3),("cfg_scale_caption","声の説明の反映度",4),("cfg_scale_speaker","お手本の声の反映度",5)]:
                                controls[name] = gr.Slider(0,10,value=value,step=0.1,label=label,info="上げすぎると不自然になる場合があります。")
                with gr.Accordion("詳細設定（通常は変更不要）", open=True) as advanced_settings:
                    with gr.Tabs():
                        with gr.Tab("機器・計算方式",render_children=True):
                            with gr.Row(elem_classes="settings-page"):
                                with gr.Column():
                                    for name,label in [("model_device","音声生成"),("codec_device","音声変換")]:
                                        controls[name] = gr.Dropdown(devices,value=device,label=label+"に使う機器",info="cuda・xpuはGPU、cpuはCPUを使用します。")
                                        precision_name = name.replace("device","precision")
                                        controls[precision_name] = gr.Dropdown(precisions,value=precisions[0],label=label+"の計算精度",info="通常は初期値で使ってください。")
                                        controls[name].change(upstream._on_model_device_change,controls[name],controls[precision_name])
                                with gr.Column():
                                    controls["t_schedule_mode"] = gr.Dropdown([("標準","linear"),("Sway（実験的）","sway")],value="linear",label="計算の進め方")
                                    controls["sway_coeff"] = gr.Slider(-1,1.5,value=-1,step=0.1,interactive=False,label="Swayの調整値",info="Swayを選んだ場合だけ使います。")
                                    controls["t_schedule_mode"].change(upstream._on_t_schedule_mode_change,controls["t_schedule_mode"],controls["sway_coeff"])
                                    controls["cfg_guidance_mode"] = gr.Dropdown([("個別","independent"),("一括","joint"),("交互","alternating")],value="independent",label="条件を反映する方式")
                                    controls["context_kv_cache"] = gr.Checkbox(value=True,label="共通の計算結果を再利用する")
                                    unload = gr.Button("モデルをメモリから解放")
                                    gr.Markdown("ダウンロード済みファイルは残ります。次回生成時に再読み込みします。")
                        with gr.Tab("内部補正・追加学習",render_children=True):
                            with gr.Row(elem_classes="settings-page"):
                                with gr.Column():
                                    for name,label in [("cfg_scale_raw","反映度の一括上書き"),("speaker_kv_scale_raw","お手本の内部補正値"),("max_text_len_raw","文章の処理上限（トークン数）"),("max_caption_len_raw","説明の処理上限（トークン数）")]:
                                        controls[name] = gr.Textbox(label=label,info="通常は空欄にしてください。")
                                with gr.Column():
                                    for name,label in [("truncation_factor_raw","ノイズの打ち切り係数"),("rescale_k_raw","再スケーリング係数"),("rescale_sigma_raw","再スケーリングの強さ"),("lora_adapter_raw","LoRAフォルダの場所")]:
                                        controls[name] = gr.Textbox(label=label,info="通常は空欄にしてください。")
                                with gr.Column():
                                    controls["cfg_min_t"] = gr.Number(value=0.5,label="条件反映の開始位置",info="初期値は0.5です。")
                                    controls["cfg_max_t"] = gr.Number(value=1,label="条件反映の終了位置",info="初期値は1です。")
                with gr.Accordion("実行記録（問い合わせ用）", open=False):
                    log = gr.Textbox(label="詳しい実行記録（一部英語）",interactive=False,lines=10,max_lines=10)
            with gr.Tab("読み辞書",render_children=True) as dictionary_tab:
                with gr.Column(elem_id="dictionary-wide"):
                    dictionary_listing,dictionary_outputs = build_dictionary_tab()
            option_controls=opt.build_options()
            with gr.Tab("クレジット・利用条件",render_children=True):
                gr.Markdown(footer_text(),elem_id="credits-page")
        keys = list(inspect.signature(upstream._run_generation).parameters)
        if set(keys) != set(controls):
            raise RuntimeError(f"UI input mismatch: {set(keys) ^ set(controls)}")
        base_generate=compact_generation(upstream,keys)
        def protected_generate(*args):
            with opt.LOCK:
                yield from base_generate(*args)
        generate.click(protected_generate,[mode,dictionary_enabled,speed]+[controls[k] for k in keys],
                       [audio,download,selected_audio,paths,status,log],concurrency_id="synthesis")
        def choose_audio(index,values):
            if index is None or not values:
                return None,gr.update(value=None,visible=False)
            path = values[int(index)]
            return path,gr.update(value=path,visible=True)
        selected_audio.input(choose_audio,[selected_audio,paths],[audio,download],queue=False)
        def release():
            before = mem.process_gb()
            upstream._clear_runtime_cache()
            upstream._easy_last_key = None
            mem.release()
            gr.Info("モデルをメモリから解放しました。")
            return "モデルをメモリから解放しました。次回生成時に再読み込みします。\n" + mem.summary(before)
        unload.click(release,outputs=status,concurrency_id="synthesis")
        rf_names=['cfg_scale_text','cfg_scale_caption','cfg_scale_speaker','cfg_guidance_mode','t_schedule_mode','sway_coeff','cfg_scale_raw','speaker_kv_scale_raw','cfg_min_t','cfg_max_t','truncation_factor_raw','rescale_k_raw','rescale_sigma_raw']
        restored_model=opt.restore().get('values',{})
        model_state=gr.State(value=dict(previous=restored_model.get('checkpoint',MODELS[0][1]),steps={restored_model.get('checkpoint',MODELS[0][1]):restored_model.get('num_steps',40)}))
        def switch_model(model,steps,state):
            state=dict(state);saved=dict(state['steps']);saved[state['previous']]=steps
            state.update(previous=model,steps=saved);mf=model==opt.MF
            return [gr.update(value=saved.get(model,4 if mf else 40),info='MFは通常4で使用します。' if mf else '標準は40です。'),state]+[gr.update(interactive=not mf) for _ in rf_names]
        controls['checkpoint'].change(switch_model,[controls['checkpoint'],controls['num_steps'],model_state],[controls['num_steps'],model_state]+[controls[n] for n in rf_names],queue=False,show_progress='hidden')
        # Persist each edited field without waiting for hidden/uncollapsed controls.
        draft_key='easy-v12-draft-'+__import__('hashlib').sha256(str(ROOT).encode()).hexdigest()[:16]
        excluded={'ref_wavs','lora_adapter_raw','model_device','codec_device','model_precision','codec_precision'}
        saved_controls={k:c for k,c in controls.items() if k not in excluded}
        initial=dict(mode=mode.value,enabled=dictionary_enabled.value,speed=speed.value,
                     values={k:c.value for k,c in saved_controls.items()},revision=0)
        initial.update(opt.restore())
        def remember_payload(payload):
            draft=json.loads(payload)
            opt.remember(draft['mode'],draft['enabled'],draft['speed'],draft['values'],draft['revision'])
        for name,component in dict(mode=mode,enabled=dictionary_enabled,speed=speed,**saved_controls).items():
            js="""(value)=>{
                const key=KEY, name=NAME;
                let draft=INITIAL;
                try { const saved=JSON.parse(localStorage.getItem(key)||'null');
                    if(saved && saved.revision>draft.revision) draft=saved; } catch(_) {}
                if(['mode','enabled','speed'].includes(name)) draft[name]=value;
                else {
                    if(name==='checkpoint' && draft.values.checkpoint!==value){
                        draft.modelSteps={...draft.modelSteps,[draft.values.checkpoint]:draft.values.num_steps};
                        draft.values.num_steps=draft.modelSteps[value]??(value===MF?4:40);
                    }
                    draft.values[name]=value;
                }
                draft.revision=Math.max(Date.now()*1000,(draft.revision||0)+1);
                try {localStorage.setItem(key,JSON.stringify(draft));}catch(_){}
                return [JSON.stringify(draft)];
            }""".replace('MF',json.dumps(opt.MF)).replace('KEY',json.dumps(draft_key)).replace('NAME',json.dumps(name)).replace('INITIAL',json.dumps(initial))
            component.change(remember_payload,inputs=component,js=js,preprocess=False,
                            queue=False,trigger_mode='multiple',show_progress='hidden')
        def restore_inputs(payload):
            old=opt.recover_browser(payload);values=old.get('values',{})
            model=values.get('checkpoint',MODELS[0][1]);steps=values.get('num_steps',4 if model==opt.MF else 40)
            return [old.get('mode',gr.skip()),old.get('enabled',gr.skip()),old.get('speed',gr.skip())]+[gr.update(value=values[k],visible=True) if k in values else gr.update(visible=True) for k in saved_controls]+[dict(previous=model,steps={model:steps})]
        # Capture text immediately, including paste/IME input before Gradio dispatches change.
        text_fields={}
        for name,component in saved_controls.items():
            if isinstance(component,gr.Textbox):
                component.elem_id=component.elem_id or 'easy-draft-'+name
                text_fields[component.elem_id]=name
        load_js="""()=>{
            const key=KEY, initial=INITIAL, fields=FIELDS;
            let draft=initial;
            try {const saved=JSON.parse(localStorage.getItem(key)||'null');
                if(RESTORE && saved && saved.revision>draft.revision)draft=saved;
                localStorage.setItem(key,JSON.stringify(draft));}catch(_){}
            const listenerKey=key+'-listener';
            if(window[listenerKey])document.removeEventListener('input',window[listenerKey],true);
            window[listenerKey]=(event)=>{
                const target=event.target;
                if(!(target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement))return;
                for(const [id,name] of Object.entries(fields))if(target.closest('[id="'+id+'"]')){
                    try {const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved)draft=saved;}catch(_){}
                    draft.values[name]=target.value;
                    draft.revision=Math.max(Date.now()*1000,(draft.revision||0)+1);
                    try {localStorage.setItem(key,JSON.stringify(draft));}catch(_){}
                    break;
                }
            };
            document.addEventListener('input',window[listenerKey],true);
            return [JSON.stringify(draft)];
        }""".replace('RESTORE',json.dumps(opt.read()['restore_input'])).replace('KEY',json.dumps(draft_key)).replace('FIELDS',json.dumps(text_fields)).replace('INITIAL',json.dumps(initial))
        # JS supplies the payload; no hidden component must mount before startup.
        demo.load(restore_inputs,inputs=mode,outputs=[mode,dictionary_enabled,speed]+list(saved_controls.values())+[model_state],
                  js=load_js,preprocess=False,queue=False,show_progress='hidden')
        demo.load(fn=None,inputs=option_controls['theme'],outputs=None,js=opt.THEME_JS)
        demo.load(fn=None, js=VOLUME_JS)
        demo.load(lambda: [gr.update(open=False),gr.update(open=False)], outputs=[generation_settings,advanced_settings],queue=False,show_progress="hidden")
        demo.load(dictionary_listing,outputs=dictionary_outputs,queue=False,show_progress="hidden")
        dictionary_tab.select(dictionary_listing,outputs=dictionary_outputs,queue=False,show_progress="hidden")
    return demo
CSS += """
.dark #easy-hero,.dark #easy-hero *{background:#20382c!important;color:#d9eee2!important}
"""

CSS += ".v12-option{padding:18px!important;border:1px solid #8899aa66!important;border-radius:12px!important;margin-bottom:16px!important}.v12-option .prose{background:transparent!important}"