import os
import subprocess
import time
from pathlib import Path
from yt_dlp import YoutubeDL
import flet as ft
import re
from tkinter import Tk, filedialog
import sys


# スクリプトのパスを取得
current_dir = Path(__file__).parent

# ダウンロードと変換のフォルダ
download_directory = ''
output_folder = download_directory  # 出力フォルダもダウンロードフォルダと同じに設定

def check_media_file_exists(directory):
    return any(filename.endswith(('.webm', '.mkv', '.ogg', '.flv', '.mp4', '.avi', '.mov', '.qt', '.mpg', 'mpeg', '.asf', '.vob', '.wmv', '.m4a')) for filename in os.listdir(directory))

def check_signal_file_exists(directory):
    signal_file_path = os.path.join(directory, 'done.txt')
    return os.path.isfile(signal_file_path)

def create_folder_if_not_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()

def convert_media_to_mp4(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    base_folder = os.path.join(output_folder, sanitize_filename(base_name))
    output_file = os.path.join(base_folder, sanitize_filename(base_name) + '.mp4')
    audio_file = os.path.join(base_folder, sanitize_filename(base_name) + '_audio.wav')
    
    create_folder_if_not_exists(base_folder)
    
    if os.path.exists(output_file):
        print(f'Skipped (already exists): {output_file}')
        return
    
    command_mp4 = [
        'ffmpeg', 
        '-i', file_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '320k',
        output_file
    ]
    
    command_audio = [
        'ffmpeg',
        '-i', file_path,
        '-vn',
        '-ar', '48000',
        '-sample_fmt', 's16',
        '-ac', '2',
        audio_file
    ]
    
    try:
        subprocess.run(command_mp4, check=True, stderr=subprocess.PIPE)
        print(f'Converted video: {output_file}')
        
        subprocess.run(command_audio, check=True, stderr=subprocess.PIPE)
        print(f'Extracted audio: {audio_file}')
        
        moved_file_path = os.path.join(base_folder, os.path.basename(file_path))
        os.rename(file_path, moved_file_path)
        print(f'Moved original file to: {moved_file_path}')
        
        os.remove(moved_file_path)
        print(f'Deleted original file: {moved_file_path}')
    
    except subprocess.CalledProcessError as e:
        print(f'Error during conversion: {e.stderr.decode()}')

def remove_signal_file(directory):
    signal_file_path = os.path.join(directory, 'done.txt')
    if os.path.isfile(signal_file_path):
        os.remove(signal_file_path)
        print(f'Removed signal file: {signal_file_path}')

def open_folder_dialog():
    root = Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(title="ダウンロード先を選択")
    return folder_selected if folder_selected else None

def main(page: ft.Page):
    page.title = "YoutubeDownloader"
    page.window_height = 371
    page.window_width = 600

    def close_dlg(e):
        err_dlg.open = False
        downloadButton.disabled = False
        progressBar.value = 200
        progressText.value = "エラーで終了しました。"
        page.update()

    err_dlg = ft.AlertDialog(
        title=ft.Text("エラー"),
        modal=True,
        content=ft.Text("エラーメッセージ"),
        actions=[ft.TextButton("閉じる", on_click=close_dlg)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def showError(errMsg):
        err_dlg.content = ft.Text(errMsg)
        page.dialog = err_dlg
        err_dlg.open = True
        page.update()

    def logHook(d):
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes")
            downloaded_bytes = d.get("downloaded_bytes")
            if total_bytes and total_bytes > 0:
                percent = (downloaded_bytes / total_bytes) * 100
                progressBar.value = percent
            else:
                progressBar.value = None
            progressText.value = f"ダウンロード中... {d.get('_default_template', '')}"
            progressText.update()
            progressBar.update()
        elif d["status"] == "finished":
            progressBar.value = 100
            progressText.value = "ダウンロード完了"
            signal_file_path = os.path.join(download_directory, 'done.txt')
            with open(signal_file_path, 'w') as f:
                f.write('Download complete')

    def getMetaData():
        try:
            with YoutubeDL() as ydl:
                res = ydl.extract_info(videoUrl.value, download=False)
                return res
        except Exception as e:
            showError(f"メタデータ取得エラーが発生しました: {str(e)}")

    def videoDownload(e):
        try:
            if not videoUrl.value:
                showError("動画URLが入力されていません。")
                return
            downloadButton.disabled = True
            progressBar.value = None
            progressText.value = "ダウンロード開始処理中... "
            page.update()

            metaData = getMetaData()
            if metaData:
                title = sanitize_filename(metaData.get("title", "Untitled"))
                output_path = os.path.join(download_directory, title)

                ydl_opts_video = {
                    'progress_hooks': [logHook],
                    'format': 'bestvideo+bestaudio/best',
                    'outtmpl': output_path,
                }

                with YoutubeDL(ydl_opts_video) as ydl:
                    ydl.download([videoUrl.value])

                progressText.value = "ダウンロード完了。変換中..."
                page.update()
            
                while not check_media_file_exists(download_directory):
                    time.sleep(5)
            
                while not check_signal_file_exists(download_directory):
                    time.sleep(5)

                for file_name in os.listdir(download_directory):
                    if file_name.endswith(('.webm', '.mkv', '.ogg', '.flv')):
                        file_path = os.path.join(download_directory, file_name)
                        convert_media_to_mp4(file_path)
            
                remove_signal_file(download_directory)
                progressBar.value = 100
                progressText.value = "変換完了。"
                page.update()

            downloadButton.disabled = False
            page.update()

        except Exception as e:
            showError(f"ビデオダウンロード中取得エラーが発生しました: {str(e)}")

    def changeDownloadFolder(e):
        global download_directory, output_folder
        new_folder = open_folder_dialog()
        if new_folder:
            download_directory = new_folder
            output_folder = new_folder
            downloadFolder.value = download_directory
            page.update()

    progressBar = ft.ProgressBar(width=page.window_width - 20, value=0)
    progressText = ft.Text(value="")
    videoUrl = ft.TextField(label="動画URL", value="", expand=True)
    downloadFolder = ft.TextField(label="保存先", value=download_directory, expand=True, read_only=True)
    changeFolderButton = ft.FilledButton(text="保存先変更", on_click=changeDownloadFolder)
    downloadButton = ft.ElevatedButton(text="ダウンロード", on_click=videoDownload, width=120, height=60)

    pageColumn = ft.Column(
        [
            ft.Row([videoUrl], alignment=ft.MainAxisAlignment.START),
            ft.Row([downloadFolder, changeFolderButton], alignment=ft.MainAxisAlignment.START),
            downloadButton,
            progressBar,
            progressText,
        ],
        alignment=ft.MainAxisAlignment.START,
        scroll=ft.ScrollMode.ALWAYS,
        height=page.window_height - 60
    )
    
    page.add(pageColumn)

    def page_resize(e):
        pageColumn.height = page.window_height - 60
        progressBar.width = page.window_width - 20
        page.update()

    page.on_resize = page_resize

    def on_close(e):
        sys.exit(0)

    page.on_close = on_close

ft.app(target=main)
