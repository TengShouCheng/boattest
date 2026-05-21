# 高千穗划船 6/4 名額監控

## 1. 建立 Pushover
1. 到 Pushover 註冊並登入
2. 安裝 Pushover 手機 App
3. 建立一個 Application，取得 `API Token/Key`
4. 帳號首頁取得 `User Key`

## 2. 建立 GitHub Repository
建立一個 private repository，把本資料夾所有檔案放上去。

## 3. 設定 GitHub Secrets
Repository → Settings → Secrets and variables → Actions → New repository secret

新增：
- `PUSHOVER_USER_KEY`
- `PUSHOVER_APP_TOKEN`

## 4. 啟動測試
到 Actions → Check Takachiho boat availability → Run workflow

之後會每 10 分鐘檢查一次。

## 5. 注意
- 程式只做通知，不自動下單或付款。
- GitHub Actions 排程可能延遲，不保證秒級準時。
- 若網站改版，可能要調整 `monitor_takachiho.py` 的偵測關鍵字或點擊邏輯。
