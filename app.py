#!/bin/python

from flask import Flask, render_template, request, jsonify
import metadata
from ncmdump import dump
from api import NCMApi
import sys
import os
import re
import json

PLAYLIST_DIR = "/app/playlist"
NCM_DIR = "/app/ncm"
SCRAPE_DIR = "/app/scrape"


def check_directory_mounted(directory):
    if not os.path.exists(directory):
        print(f"⚠目录 {directory} 不存在，请确保挂载了 Volume！")
        return False
    if not os.listdir(directory):
        print(f"⚠目录 {directory} 为空，可能未正确挂载 Volume！")
        return False
    return True


if not all([
    check_directory_mounted(PLAYLIST_DIR),
    check_directory_mounted(NCM_DIR),
    check_directory_mounted(SCRAPE_DIR),
]):
    print("❌ 检测到未挂载 Volume，程序可能无法正常运行！")
    sys.exit(1)

app = Flask(__name__)

# 初始化NCM API
ncm_api = NCMApi()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/playlist", methods=['POST'])
def get_playlist():
    """获取歌单信息"""
    try:
        data = request.get_json()
        playlist_input = data.get('playlistUrl', '').strip()
        
        if not playlist_input:
            return jsonify({'status': 'error', 'message': '请输入歌单URL或ID'})
        
        # 从URL中提取歌单ID
        playlist_id = extract_playlist_id(playlist_input)
        if not playlist_id:
            return jsonify({'status': 'error', 'message': '无效的歌单URL或ID'})
        
        # 获取歌单信息
        playlist_info = ncm_api.get_playlist_info(playlist_id)
        
        if playlist_info.get('status') != 'success':
            return jsonify({'status': 'error', 'message': '获取歌单信息失败'})
        
        # 获取歌单中的歌曲详细信息
        songs = []
        for song_id in playlist_info['trackIds']:
            song_info = ncm_api.get_song_info(song_id)
            if song_info.get('status') == 'success':
                songs.append({
                    'id': song_id,
                    'title': song_info['name'],
                    'artist': ', '.join(song_info['artists']),
                    'album': song_info['album_name'],
                    'cover': song_info['picUrl'],
                    'duration': '00:00'  # 默认时长，实际应该从API获取
                })
        
        result = {
            'status': 'success',
            'data': {
                'name': playlist_info['name'],
                'desc': f'创建者: {playlist_info["creator"]}',
                'cover': songs[0]['cover'] if songs else '',
                'songs': songs,
                'total': playlist_info['song_num']
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'})


@app.route("/api/download", methods=['POST'])
def download_songs():
    """下载歌曲"""
    try:
        data = request.get_json()
        song_ids = data.get('songIds', [])
        playlist_name = data.get('playlistName', '未知歌单')
        if not os.path.exists(f"{PLAYLIST_DIR}/{playlist_name}"):
            os.mkdir(f"{PLAYLIST_DIR}/{playlist_name}")
        
        if not song_ids:
            return jsonify({'status': 'error', 'message': '请选择要下载的歌曲'})

        dl_status = []
        song_results = []

        for song_id in song_ids:
            song_info = ncm_api.get_song_info(str(song_id))
            is_succeed, audio_data = ncm_api.get_mp3_data(str(song_id))
            
            song_result = {
                'songId': song_id,
                'success': False,
                'message': ''
            }
            
            if is_succeed:
                if song_info.get("status") == "success":
                    try:
                        name = song_info['name']
                        artists_list = song_info['artists']
                        artists = ''
                        for j in artists_list:
                            artists += j + ","
                        artists = artists[:-1]
                        album_name = song_info['album_name']
                        pic_url = song_info['picUrl']
                        full_path = generate_file_path(name, artists, playlist_name) + ".mp3"
                        with open(full_path, "wb") as file:
                            file.write(audio_data.content)
                        metadata.meta_data(full_path, name, artists_list, album_name, pic_url)
                        song_result['success'] = True
                        song_result['message'] = '下载成功'
                    except Exception as e:
                        song_result['message'] = f'保存文件失败: {str(e)}'
                else:
                    song_result['message'] = '获取歌曲信息失败'
            else:
                song_result['message'] = '获取音频数据失败'
            
            dl_status.append(is_succeed)
            song_results.append(song_result)

        # 统计下载结果
        success_count = sum(1 for status in dl_status if status)
        failed_count = len(dl_status) - success_count
        
        result = {
            'status': 'success',
            'message': f'下载完成！成功 {success_count} 首，失败 {failed_count} 首',
            'data': {
                'total': len(song_ids),
                'downloaded': success_count,
                'failed': failed_count,
                'playlistName': playlist_name,
                'songResults': song_results
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'下载失败: {str(e)}'})


@app.route("/api/convert", methods=['POST'])
def convert_ncm():
    """转换NCM文件"""
    try:
        data = request.get_json()
        # ncm_path = data.get('ncmPath', '')
        # output_path = data.get('outputPath', '')
        
        # 检查目录是否存在
        if not os.path.exists(NCM_DIR):
            return jsonify({'status': 'error', 'message': 'NCM目录不存在'})
        elif os.path.exists(f"{NCM_DIR}/converted_mp3"):
            os.makedirs(f"{NCM_DIR}/converted_mp3")
        
        # 扫描NCM文件

        ncm_files = [f for f in os.listdir(NCM_DIR) if f.endswith(".ncm")]
        for file in ncm_files:
            filepath = NCM_DIR + "/" + file
            dump(filepath)
        
        if not ncm_files:
            return jsonify({'status': 'error', 'message': '未找到NCM文件'})
        
        result = {
            'status': 'success',
            'message': f'找到 {len(ncm_files)} 个NCM文件',
            'data': {
                'files': ncm_files,
                'total': len(ncm_files)
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'转换失败: {str(e)}'})


@app.route("/api/scrape", methods=['POST'])
def scrape_music():
    """音乐刮削"""
    try:
        data = request.get_json()
        # music_path = data.get('musicPath', '')
        # options = data.get('options', {})
        
        if not SCRAPE_DIR:
            return jsonify({'status': 'error', 'message': '请选择音乐目录'})
        
        if not os.path.exists(SCRAPE_DIR):
            return jsonify({'status': 'error', 'message': '音乐目录不存在'})
        
        # 扫描音乐文件
        mp3_files = [f for f in os.listdir(SCRAPE_DIR) if f.endswith(".mp3")]
        scrape_results = []
        
        for mp3_file in mp3_files:
            file_path = os.path.join(SCRAPE_DIR, mp3_file)
            file_size = os.path.getsize(file_path)
            
            # 尝试刮削
            try:
                song_info = ncm_api.get_song_info_by_keyword(mp3_file[:-4])
                is_succeed = song_info['status']
                
                if is_succeed == "success":
                    metadata.meta_data(SCRAPE_DIR + "/" + mp3_file, song_info["name"], song_info["artists"],
                                       song_info["album_name"], song_info["picUrl"])
                    scrape_results.append({
                        'name': mp3_file,
                        'path': file_path,
                        'size': format_file_size(file_size),
                        'status': 'success',
                        'message': '刮削成功',
                        'song_name': song_info["name"],
                        'artists': song_info["artists"],
                        'album': song_info["album_name"]
                    })
                else:
                    scrape_results.append({
                        'name': mp3_file,
                        'path': file_path,
                        'size': format_file_size(file_size),
                        'status': 'failed',
                        'message': '未找到匹配的歌曲信息',
                        'song_name': '',
                        'artists': [],
                        'album': ''
                    })
            except Exception as e:
                scrape_results.append({
                    'name': mp3_file,
                    'path': file_path,
                    'size': format_file_size(file_size),
                    'status': 'failed',
                    'message': f'刮削失败: {str(e)}',
                    'song_name': '',
                    'artists': [],
                    'album': ''
                })
        
        # 统计刮削结果
        success_count = sum(1 for result in scrape_results if result['status'] == 'success')
        failed_count = len(scrape_results) - success_count
        
        result = {
            'status': 'success',
            'message': f'刮削完成！成功 {success_count} 首，失败 {failed_count} 首',
            'data': {
                'files': scrape_results,
                'total': len(mp3_files),
                'success_count': success_count,
                'failed_count': failed_count
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'刮削失败: {str(e)}'})


def generate_file_path(name, artists, playlist_name):
    return PLAYLIST_DIR + "/" + playlist_name + "/" + name + " - " + artists


def extract_playlist_id(playlist_input):
    """从歌单URL或ID中提取歌单ID"""
    # 如果是纯数字，直接返回
    if playlist_input.isdigit():
        return playlist_input

    ids = re.findall(r'[?&]id=(\d+)', playlist_input)
    if ids:
        playlist_id = ids[0]
        return playlist_id
    
    return None


def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


# if __name__ == '__main__':
#     app.run(host="0.0.0.0", port=5266)