from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove
from asyncio import gather, create_subprocess_exec
from os import execl as osexecl
from psutil import (
    disk_usage,
    cpu_percent,
    swap_memory,
    cpu_count,
    virtual_memory,
    net_io_counters,
    boot_time,
)
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from signal import signal, SIGINT
from sys import executable
from time import time

from bot import (
    bot,
    bot_name,
    botStartTime,
    LOGGER,
    intervals,
    config_dict,
    scheduler,
    sabnzbd_client,
)
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.ext_utils.bot_utils import (
    cmd_exec,
    sync_to_async,
    set_commands,
    create_help_buttons,
    new_task,
)
from .helper.ext_utils.db_handler import database
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.jdownloader_booter import jdownloader
from .helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import send_message, edit_message, send_file
from .modules import (
    authorize,
    cancel_task,
    clone,
    speedtest,
    exec,
    file_selector,
    gd_count,
    gd_delete,
    gd_search,
    mirror_leech,
    status,
    ytdlp,
    shell,
    users_settings,
    bot_settings,
    help,
    force_start,
)


@new_task
async def stats(_, message):
    if await aiopath.exists(".git"):
        last_commit = await cmd_exec(
            "git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'", True
        )
        last_commit = last_commit[0]
    else:
        last_commit = "No UPSTREAM_REPO"

    total, used, free, disk = disk_usage("/")
    swap                       = swap_memory()
    memory                     = virtual_memory()
    bot_uptime                 = get_readable_time(time() - botStartTime)
    os_uptime                  = get_readable_time(time() - boot_time())
    upload                     = get_readable_file_size(net_io_counters().bytes_sent)
    download                   = get_readable_file_size(net_io_counters().bytes_recv)
    cpu_usage                  = cpu_percent(interval=0.5)
    ram_usage                  = memory.percent
    swap_total                 = get_readable_file_size(swap.total)
    swap_used_percent          = swap.percent
    memory_total               = get_readable_file_size(memory.total)
    memory_free                = get_readable_file_size(memory.available)
    memory_used                = get_readable_file_size(memory.used)
    physical_cores             = cpu_count(logical=False)
    total_cores                = cpu_count(logical=True)

    stats = (
        f"<b>Commit Date:</b> {last_commit}\n\n"
        f"<b>Bot Uptime:</b> {bot_uptime}\n"
        f"<b>OS Uptime:</b> {os_uptime}\n\n"
        f"<b>Total Disk Space:</b> {get_readable_file_size(total)}\n"
        f"<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}\n\n"
        f"<b>Upload:</b> {upload}\n"
        f"<b>Download:</b> {download}\n\n"
        f"<b>CPU:</b> {cpu_usage}%\n"
        f"<b>RAM:</b> {ram_usage}%\n"
        f"<b>DISK:</b> {disk}%\n\n"
        f"<b>Physical Cores:</b> {physical_cores}\n"
        f"<b>Total Cores:</b> {total_cores}\n\n"
        f"<b>SWAP:</b> {swap_total} | <b>Used:</b> {swap_used_percent}%\n"
        f"<b>Memory Total:</b> {memory_total}\n"
        f"<b>Memory Free:</b> {memory_free}\n"
        f"<b>Memory Used:</b> {memory_used}\n"
    )

    await send_message(message, stats)


from time import time
from bot import botStartTime
from .helper.common import TaskConfig


async def start(client, message):
    buttons = ButtonMaker()
    buttons.url_button("ʙᴏᴛ\nᴏᴡɴᴇʀ", "https://t.me/noob_je", "header")
    
    is_authorized = await CustomFilters.authorized(client, message)
    status = "Authorize: ✅" if is_authorized else "Authorize: ❌"

    if not is_authorized:
        buttons.url_button("ʙᴏᴛ\nʀᴇᴘᴏ", "https://github.com/zxlbni")
        
    reply_markup = buttons.build_menu(2)

    start_string = f"""
<b>Hello, I am {bot_name}</b>

I can help you mirror links, files, or torrents to Google Drive, rclone cloud, or Telegram.
Type /{BotCommands.HelpCommand} to see the list of commands.

<b>Uptime: {get_readable_time(time() - botStartTime)}</b>
<b>{status}</b>
"""

    await send_message(message, start_string, reply_markup)


@new_task
async def restart(_, message):
    intervals["stopAll"] = True
    restart_message = await send_message(message, "sek sabar...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if qb := intervals["qb"]:
        qb.cancel()
    if jd := intervals["jd"]:
        jd.cancel()
    if nzb := intervals["nzb"]:
        nzb.cancel()
    if st := intervals["status"]:
        for intvl in list(st.values()):
            intvl.cancel()
    await sync_to_async(clean_all)
    if sabnzbd_client.LOGGED_IN:
        await gather(
            sabnzbd_client.pause_all(),
            sabnzbd_client.purge_all(True),
            sabnzbd_client.delete_history("all", delete_files=True),
        )
    proc1 = await create_subprocess_exec(
        "pkill",
        "-9",
        "-f",
        "gunicorn|aria2c|qbittorrent-nox|ffmpeg|rclone|java|sabnzbdplus",
    )
    proc2 = await create_subprocess_exec("python3", "update.py")
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "Starting Ping")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"{end_time - start_time} ms")


@new_task
async def log(_, message):
    await send_file(message, "log.txt")

help_string = f"""
NOTE: Try each command without any argument to see more detalis.<blockquote expandable>
/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Start mirroring to cloud.
/{BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Start Mirroring to cloud using qBittorrent.
/{BotCommands.JdMirrorCommand[0]} or /{BotCommands.JdMirrorCommand[1]}: Start Mirroring to cloud using JDownloader.
/{BotCommands.NzbMirrorCommand[0]} or /{BotCommands.NzbMirrorCommand[1]}: Start Mirroring to cloud using Sabnzbd.
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Start leeching to Telegram.
/{BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Start leeching using qBittorrent.
/{BotCommands.JdLeechCommand[0]} or /{BotCommands.JdLeechCommand[1]}: Start leeching using JDownloader.
/{BotCommands.NzbLeechCommand[0]} or /{BotCommands.NzbLeechCommand[1]}: Start leeching using Sabnzbd.
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leech yt-dlp supported link.
/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive.
/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).
/{BotCommands.UserSetCommand[0]} or /{BotCommands.UserSetCommand[1]} [query]: Users settings.
/{BotCommands.BotSetCommand[0]} or /{BotCommands.BotSetCommand[1]} [query]: Bot settings.
/{BotCommands.SelectCommand}: Select files from torrents or nzb by gid or reply.
/{BotCommands.CancelTaskCommand} [gid]: Cancel task by gid or reply.
/{BotCommands.ForceStartCommand[0]} or /{BotCommands.ForceStartCommand[1]} [gid]: Force start task by gid or reply.
/{BotCommands.CancelAllCommand} [query]: Cancel all [status] tasks.
/{BotCommands.ListCommand} [query]: Search in Google Drive(s).
/{BotCommands.SearchCommand} [query]: Search for torrents with API.
/{BotCommands.StatusCommand}: Shows a status of all the downloads.
/{BotCommands.StatsCommand}: Show stats of the machine where the bot is hosted in.
/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot (Only Owner & Sudo).
/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UsersCommand}: show users settings (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).
/{BotCommands.RestartCommand}: Restart and update the bot (Only Owner & Sudo).
/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/{BotCommands.ShellCommand}: Run shell commands (Only Owner).
/{BotCommands.AExecCommand}: Exec async functions (Only Owner).
/{BotCommands.ExecCommand}: Exec sync functions (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clear {BotCommands.AExecCommand} or {BotCommands.ExecCommand} locals (Only Owner).
/{BotCommands.RssCommand}: RSS Menu.</blockquote>
"""


@new_task
async def bot_help(_, message):
    await send_message(message, help_string)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incomplete_task_message(cid, msg):
        try:
            if msg.startswith("Restarted Successfully!"):
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id, text=msg
                )
                await remove(".restartmsg")
            else:
                await bot.send_message(
                    chat_id=cid,
                    text=msg,
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        except Exception as e:
            LOGGER.error(e)

    if config_dict["INCOMPLETE_TASK_NOTIFIER"] and config_dict["DATABASE_URL"]:
        if notifier_dict := await database.get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = "Restarting Done.." if cid == chat_id else "Bot Restarted!"
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg)
                            msg = ""
                if msg:
                    await send_incomplete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text="Restarting Done.."
            )
        except:
            pass
        await remove(".restartmsg")


async def main():
    if config_dict["DATABASE_URL"]:
        await database.db_load()
    await gather(
        jdownloader.initiate(),
        sync_to_async(clean_all),
        bot_settings.initiate_search_tools(),
        restart_notification(),
        telegraph.create_account(),
        rclone_serve_booter(),
        sync_to_async(start_aria2_listener, wait=False),
        set_commands(bot),
    )
    create_help_buttons()

    bot.add_handler(
        MessageHandler(
            start, filters=command(BotCommands.StartCommand, case_sensitive=True)
        )
    )
    bot.add_handler(
        MessageHandler(
            log,
            filters=command(BotCommands.LogCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    bot.add_handler(
        MessageHandler(
            restart,
            filters=command(BotCommands.RestartCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    bot.add_handler(
        MessageHandler(
            ping,
            filters=command(BotCommands.PingCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    bot.add_handler(
        MessageHandler(
            bot_help,
            filters=command(BotCommands.HelpCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    bot.add_handler(
        MessageHandler(
            stats,
            filters=command(BotCommands.StatsCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    LOGGER.info("ZyradLeechBot: lets't get party Started!")
    signal(SIGINT, exit_clean_up)


bot.loop.run_until_complete(main())
bot.loop.run_forever()
