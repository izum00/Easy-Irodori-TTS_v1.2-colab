# Easy-Irodori-TTS v1.2 (Google Colab版)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/izum00/Easy-Irodori-TTS_v1.2-colab/blob/main/Easy_Irodori_TTS_v1.2_Colab.ipynb)

Easy-Irodori-TTS v1.2（制作：ゆうぷろ with Codex）を Google Colab の GPU で動かすための版です。
**ベース / Anime / MF（高速）** のすべてのモデルに対応しています。公開リンク（`share=True`）が発行されます。

## 使い方
1. 上のバッジから `Easy_Irodori_TTS_v1.2_Colab.ipynb` を Colab で開く
2. 「ランタイム → ランタイムのタイプを変更」で **GPU** を選ぶ
3. ① セットアップ → （任意）② Googleドライブ → ③ 起動 の順にセルを実行
4. ③の出力に出る `https://〜.gradio.live` を開く

セットアップ時にこのリポジトリをGitHubからダウンロードし、本家 [Aratako/Irodori-TTS](https://github.com/Aratako/Irodori-TTS)（固定リビジョン）も取得します。

## Windows版からの主な変更点
- `.bat` / `.ps1` を削除し、Colab用ノートブック（`.ipynb`）を追加
- GPU（CUDA / PyTorch cu128）で動作。ffmpeg は apt で導入
- 起動は常に `share=True`（公開リンク）
- フォルダ選択ダイアログ・ごみ箱への移動を廃止（内部音声の整理は「削除」に変更）
- 保存先にGoogleドライブを指定可能（ノートブック②）

## ファイル構成
リポジトリ直下に以下を置いてください。

```
Easy_Irodori_TTS_v1.2_Colab.ipynb
easy_launcher.py  easy_ui.py  easy_options.py  easy_audio.py
easy_export.py  easy_cleanup.py  easy_dictionary.py  easy_text_tools.py
README.md  .gitignore
```

## ライセンス・注意事項
MIT License。音声エンジン・ベース・MF：Aratako / Irodori-TTS、Anime：phasefield-audio。
本人の同意なしの声の複製公開、なりすまし、人をだます目的での利用は禁止です。生成物は利用者の責任で使用してください。
各モデルの[ベース](https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small#license--ethical-restrictions)・[Anime](https://huggingface.co/phasefield-audio/Irodori-TTS-v4.1-Anime#license)の利用条件もご確認ください。
