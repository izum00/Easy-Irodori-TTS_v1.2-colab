"""Local settings and output management for the compact edition."""
import json,os,threading,shutil,uuid
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import gradio as gr
ROOT=Path(__file__).resolve().parent
LOCK=threading.Lock()
MF='Aratako/Irodori-TTS-v4.1-Small-MF'
DEFAULTS=dict(theme='system',restore_input=False,unload_after=False,auto_export=True,custom_output=False,output_dir='',custom_pattern=False,pattern='$連番$_$日付$',txt=False)
def read():
    path=ROOT/'config/settings.json'
    result=dict(DEFAULTS)
    if path.exists():result.update(json.loads(path.read_text(encoding='utf-8-sig')))
    return result

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

def save(values):
    with LOCK:
        result=read()
        for key in DEFAULTS:
            if key in values:
                if isinstance(DEFAULTS[key],bool) and not isinstance(values[key],bool):raise ValueError('設定値が不正です。')
                result[key]=values[key]
        if result['theme'] not in ('light','dark','system'):raise ValueError('配色が不正です。')
        if result['custom_output'] and not Path(result['output_dir']).is_absolute():raise ValueError('保存先は / から始まるフルパスで指定してください。')
        if not str(result['pattern']).strip():raise ValueError('ファイル名を指定してください。')
        atomic(ROOT/'config/settings.json',result)
    return '設定を保存しました。（Colabのセッションが終了すると、保存先がDriveでない限り設定とファイルは消えます）'

def restore():
    p=ROOT/'config/previous_input.json'
    return json.loads(p.read_text(encoding='utf-8')) if read()['restore_input'] and p.exists() else {}

INPUT_LOCK=threading.Lock()
def remember(mode,enabled,speed,params,revision=0):
    values={k:v for k,v in params.items() if k not in ('ref_wavs','lora_adapter_raw','model_device','codec_device','model_precision','codec_precision')}
    with INPUT_LOCK:
        path=ROOT/'config/previous_input.json'
        old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if revision and old.get('revision',0)>=revision:return
        atomic(path,dict(mode=mode,enabled=enabled,speed=speed,values=values,revision=revision))

def recover_browser(payload):
    if not read()['restore_input']:return {}
    if payload:
        try:cached=json.loads(payload)
        except (ValueError,TypeError):cached=None
        if isinstance(cached,dict) and isinstance(cached.get('values'),dict) and all(k in cached for k in ('mode','enabled','speed')):
            remember(cached['mode'],cached['enabled'],cached['speed'],cached['values'],cached.get('revision',0))
    return restore()


def export(paths,settings,text):
    from easy_export import export_audio,filename
    date=settings.get('_generation_date') or datetime.now().strftime('%Y%m%d_%H%M%S')
    messages=[];named=[]
    folder=ROOT/'outputs/internal'/('download_'+uuid.uuid4().hex)
    folder.mkdir(parents=True,exist_ok=True)
    for i,path in enumerate(paths,1):
        name=filename(settings,dict(text=text),dict(name=''),i,date)+'.wav'
        if settings['auto_export']:
            try:
                result=export_audio(ROOT,path,settings,dict(text=text),dict(name=''),i,date)
                if result.get('wav'):name=Path(result['wav']).name
                messages.append(result.get('error') or result['wav'])
            except Exception as exc:messages.append('自動保存に失敗しました。ダウンロードで保存してください：'+str(exc))
        # One directory per candidate also preserves identical custom names safely.
        target=folder/str(i)/name;target.parent.mkdir()
        shutil.copyfile(path,target);named.append(str(target))
    if not settings['auto_export']:messages.append('自動保存はOFFです。試聴用音声は保持しています。')
    return named,'\n'.join(messages)


def cleanup_preview():
    from easy_cleanup import inventory
    records,stamp=inventory(SimpleNamespace(root=ROOT,voices=[]))
    return f"対象：{len(records)}件 / {sum(x['size'] for x in records)/1024/1024:.1f} MB\n"+'\n'.join(x['name'] for x in records),stamp,gr.update(interactive=bool(records))

def cleanup(stamp):
    from easy_cleanup import recycle
    if not LOCK.acquire(blocking=False):raise gr.Error('音声生成が終わってから整理してください。')
    try:
        count=recycle(SimpleNamespace(root=ROOT,voices=[]),stamp)
        return f'{count}件を削除しました。',None,gr.update(interactive=False)
    finally:LOCK.release()

THEME_JS="""(choice)=>{
    if(window.easyThemeCleanup) window.easyThemeCleanup();
    const media=window.matchMedia('(prefers-color-scheme: dark)');
    const apply=()=>{
        const dark=choice==='dark'||(choice==='system'&&media.matches);
        const targets=new Set([document.documentElement,document.body,...document.querySelectorAll('gradio-app,.gradio-container')]);
        document.querySelectorAll('.gradio-container').forEach(root=>{
            for(let node=root.parentElement;node;node=node.parentElement)targets.add(node);
        });
        targets.forEach(root=>{
            if(root.classList.contains('dark')!==dark)root.classList.toggle('dark',dark);
            root.style.colorScheme=dark?'dark':'light';
        });
    };
    const observer=new MutationObserver(apply);
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    media.addEventListener('change',apply);
    apply();
    window.easyThemeCleanup=()=>{observer.disconnect();media.removeEventListener('change',apply);};
}"""

def build_options():
    settings=read();controls={}
    with gr.Tab('オプション設定',render_children=True):
        gr.Markdown('## オプション設定\n変更後は「設定を保存」を押してください。')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### 画面の配色')
            controls['theme']=gr.Dropdown([('ライト','light'),('ダーク','dark'),('PCの設定に合わせる','system')],value=settings['theme'],label='配色',elem_id='easy-theme')
            gr.Markdown('選択するとすぐに試せます。保存すると次回にも反映します。')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### 入力の復元')
            controls['restore_input']=gr.Checkbox(settings['restore_input'],label='前回の入力を復元する')
            gr.Markdown('お手本の音声は再選択してください。辞書とオプションは常に保持します。')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### メモリ（RAM）の節約')
            gr.Markdown('生成のたびに、不要なRAMとGPUキャッシュは自動で解放します。それでもRAMが足りないときは、下をONにしてください。')
            controls['unload_after']=gr.Checkbox(settings['unload_after'],label='生成が終わるたびにモデルもメモリから解放する（次の生成は読み込みのぶん遅くなります）')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### 音声の自動保存先')
            controls['auto_export']=gr.Checkbox(settings['auto_export'],label='生成した音声を自動保存する')
            gr.Markdown('OFFでも内部の試聴用音声は保持され、ダウンロードできます。')
            controls['custom_output']=gr.Checkbox(settings['custom_output'],label='保存先を指定する（OFF：Easy-Irodori-TTS_v1.2-colab/outputs/exports）')
            controls['output_dir']=gr.Textbox(settings['output_dir'],label='保存先フォルダ')
            gr.Markdown('Googleドライブに保存するには、ノートブックでドライブを接続し、例：`/content/drive/MyDrive/IrodoriTTS` のようにフルパスで指定します。')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### 保存するファイル名')
            controls['custom_pattern']=gr.Checkbox(settings['custom_pattern'],label='名前の付け方を指定する')
            controls['pattern']=gr.Textbox(settings['pattern'],label='名前の付け方')
            example=gr.Textbox(value='001_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.wav',label='名前の例',interactive=False)
            def preview(custom,pattern):
                from easy_export import filename
                return filename(dict(custom_pattern=custom,pattern=pattern),dict(text='こんにちは'),dict(name=''),1,'20260925')+'.wav'
            for token in ('$連番$','$日付$','$テキスト$'):
                b=gr.Button(token,size='sm');b.click(lambda value,t=token:value+('' if not value or value.endswith(('_',' ')) else '_')+t,controls['pattern'],controls['pattern'],queue=False)
            controls['pattern'].change(preview,[controls['custom_pattern'],controls['pattern']],example,queue=False)
            controls['custom_pattern'].change(preview,[controls['custom_pattern'],controls['pattern']],example,queue=False)
            controls['txt']=gr.Checkbox(settings['txt'],label='原文をTXTでも自動保存する')
        with gr.Group(elem_classes="v12-option"):
            gr.Markdown('### 内部音声の整理\n内部の試聴用音声を確認して削除します（Colabにはごみ箱がありません）。必要な音声は先に保存してください。元のお手本・旧版の音声・書き出し済み音声は対象外です。')
            inspect_button=gr.Button('対象の一覧と容量を確認');listing=gr.Textbox(label='整理対象',interactive=False,lines=5);stamp=gr.State(None)
            trash=gr.Button('確認した音声を削除',interactive=False)
            inspect_button.click(cleanup_preview,outputs=[listing,stamp,trash],queue=False)
            trash.click(cleanup,stamp,[listing,stamp,trash],queue=False)
        status=gr.Markdown('保存済み');button=gr.Button('設定を保存',variant='primary')
        for control in controls.values():control.change(lambda:'変更あり・未保存',outputs=status,queue=False)
        controls['theme'].change(fn=None,inputs=controls['theme'],outputs=None,js=THEME_JS,queue=False)
        button.click(lambda *values:save(dict(zip(controls,values))),list(controls.values()),status,queue=False)
    return controls