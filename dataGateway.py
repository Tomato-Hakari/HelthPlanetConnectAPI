#　ライブラリの宣言
from fastapi import FastAPI
import uvicorn
import helthplanetConnect as HPC

app = FastAPI()

# getリクエストで飛んでくる先
# helthplanetConnectでヘルスプラネットAPIと通信し、データ成型したものを取得、長さとともに送る
@app.get("/")
async def root():
    # データの取得
    data = HPC.main()
    # データの長さの取得
    length = len(data)
    # 送信
    return {'data': data, 'data_length':length}


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000, log_level="debug")
