# JARVIS v0.93｜GitHub ↔ Google Drive 最少手動授權指南

狀態：設定指南；非已連線。**不要把 Client Secret、Refresh Token、憑證 JSON 貼到 ChatGPT 或 GitHub 公開檔案。**

## 使用者只需要一次完成的設定

1. Google Cloud [啟用 Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)。
2. [Google Auth Platform](https://console.cloud.google.com/auth/overview) → Get started → Branding / Audience（個人 Gmail 使用 External）→ Data Access。若 Testing，新增自己的 Google 帳號到 Test users；長期使用前處理 Publishing status 和相關驗證要求。
3. [Clients](https://console.cloud.google.com/auth/clients) → Create client → Desktop app → 命名 JARVIS-GITHUB → Create。保管 Client ID 與 Secret。
4. [Google 官方 OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) → 右上角齒輪 → 勾 Use your own OAuth credentials → 貼自己的 Client ID / Secret（**只在 Google 網站輸入**）→ 左側手動加入 `https://www.googleapis.com/auth/drive`（此權限較廣，僅因要直接管理既有 My Drive 資料夾；將來可改成 folder-restricted app picker 流程）→ Authorize APIs → 以目標 Drive Google 帳號登入並授權 → Exchange authorization code for tokens → 複製 Refresh Token，勿貼在聊天室。
   - 若無 Refresh Token，重新以 consent prompt 取得離線授權；可核對 Playground 是否啟用 offline access。
   - 若 OAuth app 維持 External/Testing，Google Drive 的 Refresh Token 可能在 7 天到期，需處理 production 發布/驗證規定以確保長期續期。
5. [GitHub Secrets](https://github.com/danny541690/C1-RAW-DOWNLOADER/settings/secrets/actions) → New repository secret → 依序儲存：
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
   - `GOOGLE_DRIVE_FOLDER_ID`：**已核對** C1_0.93 的 01_RAW 或更合適的限定資料夾 ID；不放到公開程式碼。
6. 在 GitHub Actions 執行「Drive Credential Presence Check」，先驗證 Secret 名稱是否存在；正式上傳需另執行少量、含回讀與 SHA256 驗證的 canary，且隔離於主下載。

## 資安與條件限制
- 公開 GitHub Actions 在標準公開倉庫運作，但不要對來自 pull_request 的不受信任程式碼開放任何 Google 秘密。
- 既有 ChatGPT Drive 連線並不會授權 GitHub Actions。
- 目前 downloader 尚未進行 GitHub → Google Drive 真實 write/readback；請勿把有憑證視為已部署。
- 切勿公開 OAuth Playground 截圖的 Token 區、GitHub Secrets 值或敏感 JSON。
