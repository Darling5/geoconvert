# Release Process / 发版流程

> **Rule / 铁律：** Every release must be published to **BOTH GitHub and Gitee** — code, tag, Release and installer, none can be skipped. The in-app update check prefers the Gitee mirror (faster in China); if the Gitee release is missing, users won't see the update banner.
>
> 每次发版必须**同时**发布到 GitHub 和 Gitee——代码、tag、Release、安装包缺一不可。客户端更新检查优先走 Gitee 国内源，Gitee 缺了 Release，国内用户就收不到更新提示。

## 1. Version bump / 升版本号

| File / 文件 | Field / 字段 |
|------|------|
| `geoconvert/webui.py` | `APP_VERSION` |
| `installer.iss` | `#define MyAppVersion` |

Write the bilingual changelog to `tools/release_notes_vX.Y.Z.md` (follow the previous release notes).

## 2. Build / 打包

```powershell
python -m PyInstaller geoconvert.spec --noconfirm          # dist\geoconvert\ (onedir)
& "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe" installer.iss   # dist\geoconvert-setup-X.Y.Z.exe
```

> `pyinstaller` is not on PATH — always invoke via `python -m PyInstaller`.

## 3. Commit, tag, push to BOTH remotes / 提交、打标、双推

```powershell
git add <files>; git commit -m "..."
git tag vX.Y.Z
git push origin master vX.Y.Z     # GitHub
git push gitee  master vX.Y.Z     # Gitee (remote "gitee" = https://gitee.com/darling5/geoconvert.git)
```

## 4. GitHub Release

```powershell
gh release create vX.Y.Z dist\geoconvert-setup-X.Y.Z.exe --repo Darling5/geoconvert --title "vX.Y.Z — <summary>" --notes-file tools/release_notes_vX.Y.Z.md
```

## 5. Gitee Release (API via Python)

`curl.exe` mangles Chinese JSON on Windows (GBK) — always use a small Python script:

1. `POST https://gitee.com/api/v5/repos/darling5/geoconvert/releases`
   JSON body: `access_token`, `tag_name`, `name`, `body`, **`target_commitish` = full commit sha (required, otherwise 400)**, `prerelease: false`
2. `POST https://gitee.com/api/v5/repos/darling5/geoconvert/releases/{id}/attach_files`
   multipart form: `access_token` + `file` = the setup exe

Token: Gitee personal access token (projects scope) stored in the Windows Credential Manager (`host=gitee.com`) — never write it to any file or commit.

## 6. Verify / 发完必验

- Anonymous API must return the new tag (the repo must stay **public**, otherwise the anonymous API returns 404):
  `curl https://gitee.com/api/v5/repos/darling5/geoconvert/releases/latest`
- Silent-install the new exe once (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`) and confirm:
  - `/api/config` returns the new version
  - `/api/check-update?force=1` returns `"source": "gitee"` and the new `latest`
  - license login state and quota intact after upgrade

---

License-server deployment rules (backup / rollback / renew) are documented separately in `CHANGES-FOR-SERVER.md` — private, never committed to this repo.
