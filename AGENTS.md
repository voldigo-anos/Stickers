<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

- Keep the Telegram bot's SQLite database on Render's `/var/data` persistent disk because the container filesystem is replaced on deploy.
- Validate final decoded WhatsApp media at conversion and archive boundaries through wa_validation; encoder settings alone do not guarantee importer compliance.
- Generate Android theme wallpapers with WPS/JPEG/WPE framing because Telegram computes its wallpaper offset from WPS, not a serialized offset field.
- Keep WhatsApp choice callbacks short and resolve source pack names from user_data because Telegram callback payloads have a byte limit.
