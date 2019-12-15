# SmartMeterReceiver

スマートメーターと通信して電力使用量を取得してきて、 Prometheus に出力する Exporter

## 使用方法

- Python 3.8 以降を推奨
- prometheus-client, pyserial のライブラリが必要

以下のようなコマンドで実行

```
python sec/app.py --id <YOUR ID> --key <YOUR KEY>
```

ID と KEY に関しては、各電力会社に Bルートサービスを申し込んだ際に渡されるものが必要。
