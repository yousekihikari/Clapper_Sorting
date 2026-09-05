# Clapper Sorting

動画の冒頭に記録されたQRコードと手書きのカット数を解析し、シーンごとの振り分けとXMPサイドカーファイル作成を行うWindows向けデスクトップアプリケーションです。

## 現在の実装範囲

この初期モジュールには、PySide6によるアプリケーション骨格を含みます。

- 動画振り分け・解析タブ
- QRコード生成・印刷タブ
- 入出力フォルダ選択、解析結果テーブル、進捗表示のUI
- 冒頭最大90フレームを走査する、QThread上のQRコード解析
- OpenCV主系統＋pyzbar補助系統による日本語UTF-8 QRデコード
- 右下ROIの二値化処理と、EasyOCRの数字限定カット数認識（自動・CUDA・CPU選択）
- 解析結果のサムネイル表示と、人手でのシーン名・カット数修正
- `shutil.move` によるシーン別フォルダへの動画移動と、Premiere対応XMPサイドカー作成

QR画像生成・印刷は後続モジュールで実装します。
振り分け処理はコピーではなく、処理完了後に元動画を移動する方式
（`shutil.move`）です。

## 起動方法

Python 3.10以上を使用してください。現在の開発・検証環境は Python 3.14
(`C:\Python314\python.exe`) です。

```powershell
& 'C:\Python314\python.exe' -m pip install -r requirements.txt
& 'C:\Python314\python.exe' main.py
```

## ディレクトリ構成

```text
Clapper_Sorting/
├── main.py                    # アプリケーションのエントリーポイント
├── requirements.txt           # 実行時依存パッケージ
└── app/
    ├── main_window.py         # メインウィンドウ／タブの組み立て
    ├── models/
    │   └── analysis_result.py # 解析結果のデータモデル
    ├── views/
    │   ├── video_analysis_tab.py
    │   └── qr_generator_tab.py
    ├── workers/               # QThreadワーカー（後続モジュール）
    ├── services/              # QR・OCR・XMP・ファイル操作（後続モジュール）
    └── resources/             # アイコン等の静的リソース
```
