# tools — 投稿画像 生成エンジン

テキストを渡すと、各アカウントの絵柄そのままで投稿画像を書き出すツール群。
「毎回ゼロから手作り」を卒業し、中身（名言・解釈）だけに集中するための足場。

## akuyaku — `@悪役の言葉`（3枚組）

黒→ワインレッドの縦グラデ・明朝の悪役名言カルーセルを生成する。

```
python3 tools/akuyaku/generate.py <content.json> [出力先ディレクトリ]
```

- 出力先を省略すると `posts/<content.jsonのdate>/` に書き出す。
- 1投稿につき `NN_1.jpg`（名言＋出典）/ `NN_2.jpg`（解釈）/ `NN_3.jpg`（アウトロ）の3枚。

### content.json の形

```json
{
  "date": "2026-07-21",
  "handle": "@悪役の言葉",
  "posts": [
    {
      "quote": "名言本文（改行は自動。\\n で明示改行も可）",
      "source": "キャラ名（作品名）",
      "interpretation": "解釈・深掘りの本文"
    }
  ]
}
```

`posts` を増やせば 01, 02, 03… と連番で複数投稿を一括生成する。
サンプル: `tools/akuyaku/content.example.json`（既存の 2026-07-20 の01投稿と同じ絵になる検証用）。

## セットアップ

- Python 3 + Pillow（`pip install Pillow`）
- フォントは `tools/fonts/` に同梱（Noto Serif JP＝明朝 / Noto Sans JP＝ゴシック, SIL OFL）。

## 版面仕様（実測ベース）

- キャンバス 1080×1350（Instagram 4:5）。2倍スーパーサンプリングで文字を滑らかに。
- 色・字サイズ・余白は `posts/2026-07-20` の実測値に一致させてある。
- 再現検証：`content.example.json` から生成した画像は既存の `01_1〜01_3` とほぼ一致。

## TODO（次の一手）

- `bunkiten/` … `@bunkiten.x`（分岐点・9枚組・生成り×紺×金）の生成エンジン。フォントは同梱済み。
