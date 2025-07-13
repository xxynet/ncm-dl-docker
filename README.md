<div align="center">
<img src="./music.ico" style="text-align: center; height: 70px">

<h3>ncm-dl</h3>

Docker version of NCM-Downloader
</div>

## Screenshots

![](./Screenshots/Screenshot01.png)

![](./Screenshots/Screenshot02.png)

![](./Screenshots/Screenshot03.png)

## Deployment
In `docker-compose.yml`:
```yaml
volumes:
      - "/path/to/your/playlist/dir:/app/playlist"
      - "/path/to/your/ncm_file/dir:/app/ncm"
      - "/path/to/your/to_scrape_music/dir:/app/scrape"
```

Change these paths to where you store your music files.

```shell
docker-compose up -d
```