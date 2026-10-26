"""Dictionary editor and accessible, caret-aware emoji picker."""
from html import escape
import gradio as gr
import easy_dictionary as dictionary


def build_dictionary_tab():
    gr.Markdown("## 読み辞書\n名前や略語など、読み間違えやすい表記と読み方を登録します。登録内容は再起動しても残ります。\n\n**使い方**：表記と読み方を入力 →「登録・更新」→ 音声作成タブで生成。")
    try: initial_entries=dictionary.load()
    except ValueError: initial_entries={}
    word = gr.Textbox(label="表記", placeholder="例：Irodori", info="文章の中で置き換えたい文字です。大文字・小文字も区別します。")
    reading = gr.Textbox(label="読み方", placeholder="例：いろどり", info="ひらがな・カタカナなどで読み方を書きます。アクセントの指定機能ではありません。")
    gr.Examples([["Irodori", "いろどり"], ["TTS", "てぃーてぃーえす"], ["日本橋", "にほんばし"]], inputs=[word, reading], label="入力例（クリックで入力・登録ボタンで保存）")
    save = gr.Button("登録・更新", variant="primary")
    status = gr.Textbox(label="辞書の状態", interactive=False)
    table = gr.Dataframe(headers=["表記", "読み方"], datatype=["str", "str"], type="array", interactive=False, label="登録済みの読み方", value=list(map(list,initial_entries.items())))
    selected = gr.Dropdown(choices=list(initial_entries), label="編集・削除する登録", info="選ぶと上の入力欄に表示します。同じ表記で登録すると読み方を更新します。表記を変えると別の登録になります。")
    with gr.Row():
        remove = gr.Button("選んだ登録を削除")
        refresh = gr.Button("一覧を更新")
    gr.Markdown("**置き換えのルール**：文章中の一致する部分を置換します。長い表記を優先し、置換後の文字は再置換しません。短い表記は別の単語にも一致するため、音声作成タブのプレビューで確認してください。声の説明や元の入力文は変更しません。")

    def listing(message="辞書を読み込みました。"):
        try:
            entries = dictionary.load()
            return [[k, v] for k, v in entries.items()], gr.update(choices=list(entries), value=None), message
        except ValueError as exc:
            return [], gr.update(choices=[], value=None), str(exc)

    def mutate(action, *args):
        try:
            message = action(*args)
        except (ValueError, OSError) as exc:
            message = str(exc)
        return listing(message)

    def choose(key):
        try:
            return key or "", dictionary.load().get(key, "")
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc

    outputs = [table, selected, status]
    def save_entry(w,r):
        try:
            message=dictionary.save(w,r)
        except (ValueError,OSError) as exc:
            return (*listing(str(exc)),gr.skip(),gr.skip())
        return (*listing(message),'','')
    save.click(save_entry, [word, reading], outputs+[word,reading])
    remove.click(lambda key: mutate(dictionary.delete, key), selected, outputs)
    refresh.click(listing, outputs=outputs)
    selected.input(choose, selected, [word, reading])
    return listing, outputs


EMOJI_CATEGORIES = (
    ("ポジティブ", "楽しげ 笑い 喜び 優しく 安堵 得意げ 力強く".split()),
    ("ネガティブ", "泣き声 怒り 心配 慌てる 震え声 苦しげ 悲鳴 呆れ 舌打ち".split()),
    ("その他の感情", "驚き 疑問 照れ からかう 懇願 眠そう 酔う".split()),
    ("話し方・演出", "囁き 早口 ゆっくり 勢いよく 朗読 間 エコー 電話越し 相槌 寝言 口を塞ぐ".split()),
    ("息・口などの音", "吐息 息切れ 息をのむ あくび 喘ぎ 咳・鼻 リップノイズ 舐める音 飲み込む 嗅ぐ音 鼻歌".split()),
)


def grouped_emojis(items):
    by_label = {item.label: item for item in items}
    used = set()
    groups = []
    for title, labels in EMOJI_CATEGORIES:
        group = [by_label[label] for label in labels if label in by_label and label not in used]
        used.update(item.label for item in group)
        if group:
            groups.append((title, group))
    remaining = [item for item in items if item.label not in used]
    if remaining:
        groups.append(("その他", remaining))
    return groups


def build_emoji_picker(items=None, show_help=True):
    from irodori_tts.gradio_emoji_palette import EMOJI_PALETTE_ITEMS
    # Pointer-down keeps the textarea caret; click also supports Enter/Space activation.
    handler = """const input=document.querySelector('#irodori-voicedesign-text-input textarea');
if(!input)return;const text=input.value;const start=input.selectionStart??text.length;
const end=input.selectionEnd??start;const emoji=this.dataset.emoji;
const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
setter.call(input,text.slice(0,start)+emoji+text.slice(end));
input.dispatchEvent(new Event('input',{bubbles:true}));
input.focus({preventScroll:true});input.setSelectionRange(start+emoji.length,start+emoji.length);"""
    if show_help: gr.Markdown("文章の挿入したい場所をクリックしてから、絵文字を選んでください。文字を選択中なら、その部分を絵文字に置き換えます。効果はモデルや文脈で変わります。")
    for title, items in grouped_emojis(EMOJI_PALETTE_ITEMS if items is None else items):
        buttons = "".join(
            f'<button type="button" class="easy-emoji" data-emoji="{escape(item.emoji, quote=True)}" '
            f'aria-label="{escape(item.label, quote=True)}の絵文字を挿入" '
            f'onpointerdown="event.preventDefault()" onclick="{escape(handler, quote=True)}">'
            f'{escape(item.emoji)} {escape(item.label)}</button>' for item in items)
        gr.HTML(f'<section aria-label="{escape(title, quote=True)}">'
                f'<h4 style="margin:8px 0">{escape(title)}</h4>'
                '<div style="display:flex;flex-wrap:wrap;gap:6px">' + buttons + '</div></section>')


def preview(text, enabled):
    try:
        return dictionary.apply(text or "", enabled)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
