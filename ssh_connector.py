import logging
import traceback as tb
from threading import Thread
import logging
from typing import List
import paramiko
# from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError, AuthenticationException
import json
import random
import discord
import asyncio
from discord.ext import commands
from discord.ext.commands import Context
from discord.message import Message
import time
import os
import subprocess

#!WARNING! DEPLOY OPTION
DEPLOY = False
#!WARNING! DEPLOY OPTION

fh = logging.FileHandler('ssh.log', encoding='UTF-8')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log = logging.Logger('mlLogger', level=logging.DEBUG)

# logging.basicConfig(level=15)
# logging.addLevelName(15, 'NEWMESSAGE')
# root_logger= logging.getLogger()
# root_logger.setLevel(15) # or whatever
# handler = logging.FileHandler('handled_messages.log', 'w', 'utf-8') # or whatever
# handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')) # or whatever
# root_logger.addHandler(handler)


class Errors:
    def __init__(self, max_errors=20):
        self.errors = {}
        self.max_errors = max_errors

    def __contains__(self, code):
        if self.errors.__contains__(int(code)):
            return True
        return False

    def add_error(self, err):
        code = random.randint(1000, 9999)
        while(self.__contains__(code)):
            code = random.randint(1000, 9999)
        self.errors.update({code: err})
        if len(self.errors) > self.max_errors:
            self.errors.pop(0)
        return code

    def get_error(self, code):
        return self.errors[int(code)]

    def get_traceback(self, err_code):
        out = ''
        for el in tb.format_tb(self.errors[int(err_code)].__traceback__):
            out += el
        return "```{}```".format(out)


class Answers:
    def __init__(self, max_answers=20):
        self.answers = {}
        self.max_answers = max_answers

    def __contains__(self, code):
        if self.answers.__contains__(int(code)):
            return True
        return False

    def add_answer(self, answer):
        code = random.randint(1000, 9999)
        while(self.__contains__(code)):
            code = random.randint(1000, 9999)
        self.answers.update({code: answer})
        if len(self.answers) > self.max_answers:
            self.answers.pop(0)
        return code

    def __getitem__(self, code):
        return self.answers[int(code)]


class ChannelConnections:
    def __init__(self):
        self.connections = {}

    def append(self, channel_id, connection_id):
        # if self.connections.__contains__(channel_id):
        #     raise AssertionError("Connection id already in ChannelConnections")
        self.connections.update({channel_id: connection_id})

    def __getitem__(self, channel_id):
        return self.connections[channel_id]

    def __setitem__(self, channel_id, value):
        self.connections[channel_id] = value

    def __contains__(self, channel_id):
        return self.connections.__contains__(channel_id)

    def pop(self, channel_id):
        self.connections.pop(channel_id)

    def get_all(self):
        return self.connections


class SSHs:
    def __init__(self):
        self.sshs = {}

    def add_connection(self, ssh_connection, connection_name, channel, user_id):
        id_ = random.randint(10000, 99999)
        while self.sshs.__contains__(id_):
            id_ = random.randint(10000, 99999)
        self.sshs.update(
            {id_: {"conn": ssh_connection, "connection_name": connection_name, "channel": channel, 'user_id': user_id}})
        return id_

    def __getitem__(self, ssh_id):
        return self.sshs[ssh_id]

    def __contains__(self, ssh_id):
        if self.sshs.__contains__(ssh_id):
            return True
        return False

    def pop(self, ssh_id):
        self.sshs.pop(ssh_id)


class Lang:
    def __init__(self, lang_file_name="ssh_connector_lang.json"):
        self.lang_file_name = lang_file_name

    def __getitem__(self, code):
        with open(self.lang_file_name, 'r', encoding='UTF-8') as file:
            el = json.loads(file.read())[code]
        return el


class BlockedHosts:
    def __init__(self, file_name='blocked_hosts.json'):
        self.file_name = file_name

    def if_allowed(self, host_name, user_id):
        with open(self.file_name, 'r') as file:
            loads = json.loads(file.read())
        if not loads.__contains__(host_name):
            return True
        if loads[host_name].__contains__(user_id):
            return True
        return False


class UserRolesController:
    def __init__(self, filename: str = "allowed_roles.json") -> None:
        """User roles controller module.

        Args:
            filename (str, optional): Json filw with settings. Defaults to "allowed_roles.json".
        """
        self.filename = filename

    def _member_has_role(self, ctx: Context, role_id: int) -> bool:
        """Checks if member has role with specified role_id

        Args:
            ctx (Context): Discord context
            role_id (int): Role id

        Returns:
            bool: If member has role
        """
        specific_role = ctx.guild.get_role(role_id)  # get role
        return specific_role in ctx.message.author.roles

    def _member_has_one_of_roles(self, ctx: Context, role_ids: List[int]) -> bool:
        """Checks if member has at least one of roles

        Args:
            ctx (Context): Discord context
            role_ids (List[int]): List of role ids

        Returns:
            bool: If member has at least one of roles
        """
        for role_id in role_ids:
            if self._member_has_role(ctx, role_id):
                return True
        return False

    def author_has_allowed_role(self, ctx: Context) -> bool:
        """Checks if author has allowed role to use bot.

        Args:
            ctx (Context): Discord context.

        Returns:
            bool: If author has allowed role.
        """
        with open(self.filename, 'r') as file:
            jsoned = json.loads(file.read())
        use_checker = jsoned['use_role_checker']
        if not use_checker:
            return True
        return self._member_has_one_of_roles(ctx, jsoned["allowed_role_ids"])


Token = None  # if none then will be picked up from a token.txt
if Token is None:
    with open("token.txt", 'r') as file:
        Token = file.read()

prefix = '~'
bot = commands.Bot(command_prefix=prefix)
errors = Errors()
sshs = SSHs()
channel_connections = ChannelConnections()
answers = Answers()
lang = Lang()
blocked_hosts = BlockedHosts()
roles_controller = UserRolesController()


@bot.command(pass_context=True)
async def start(ctx: Context, ip, user, password):
    """Starts a new ssh session.

    Args:
        ip (str): Server IP
        user (str): Username
        password (str): Password
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if not blocked_hosts.if_allowed(ip, ctx.author.id):
        await ctx.send(lang["bot.command.start.error.no_permissions"].format(ip))
        return
    log.info("Запрос на соединение с {}.".format(ip))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    message = await ctx.send(lang["bot.command.start.process.starting"].format(ip))
    try:
        client.connect(hostname=ip, username=user, password=password, port=22)
        channel = client.invoke_shell()
        ssh_id = sshs.add_connection(client, ip, channel, ctx.author.id)
        channel_connections.append(ctx.channel.id, ssh_id)
        await message.edit(content=lang["bot.command.start.success.started"].format(ip, ssh_id))
        log.info("Установлено соединение с {}.".format(ip))
    except AuthenticationException:
        await ctx.send(lang["bot.command.start.error.AuthenticationException"])
        log.info("Сбой подключения к {}. Неверный пароль или логин.".format(ip))
    except NoValidConnectionsError:
        await ctx.send(lang["bot.command.start.error.NoValidConnectionsError"])
    except Exception as err:
        err_code = errors.add_error(err)
        await ctx.send(lang["bot.command.start.error.start"].format(err_code))
        log.info("Сбой подключения к {}. Неизвестная ошибка. Трэйсбэк код: {}.".format(
            ip, err_code))
        raise err


@bot.command(pass_context=True)
async def traceback(ctx: Context, code: int):
    """Gets traceback using traceback-code.

    Args:
        code (int): Traceback code.
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if not errors.__contains__(code):
        await ctx.send(lang["bot.command.traceback.error.wrong_code"])
        return
    await ctx.send(lang["bot.command.traceback.success.traceback"].format(code, errors.get_traceback(code)))


@bot.command(pass_context=True)
async def connect(ctx: Context, ssh_id):
    """Connects to a exists ssh session.

    Args:
        ssh_id (int): SSH session id.
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if sshs.__contains__(int(ssh_id)):
        channel_connections[ctx.channel.id] = int(ssh_id)
        await ctx.send(lang["bot.command.connect.success.connection_changed"].format(sshs[int(ssh_id)]["connection_name"]))
    else:
        await ctx.send(lang["bot.command.connect.error.wrong_connection_id"])


@bot.command(pass_context=True)
async def send(ctx: Context, *, command):
    """Execute command for a current ssh session

    Args:
        command (str): Command to execute
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if channel_connections.__contains__(ctx.channel.id):
        client: paramiko.SSHClient = sshs[channel_connections[ctx.channel.id]]["conn"]
        message = await ctx.send(lang["bot.command.send.process.executing"])
        try:
            # stdin, stdout, stderr = client.exec_command(command)
            # data = stdout.read() + stderr.read()
            channel = sshs[channel_connections[ctx.channel.id]]["channel"]
            channel.send(command + '\n')
            # data = channel.recv(10000)
            # if data == b'': data = lang["bot.command.send.text.no_data"].encode('UTF-8')
            # await message.delete()
            # if len(data.decode('UTF-8')) >= 400:
            #     answer_code = answers.add_answer(data.decode('UTF-8'))
            #     await ctx.send(lang["bot.command.send.success.got_answer_short"].format(data.decode('UTF-8')[:400], answer_code))
            # else:
            #     await ctx.send(lang["bot.command.send.success.got_answer"].format(data.decode('UTF-8')))
            await message.edit(content=lang["bot.command.send.success.sended"])
        except Exception as err:
            err_code = errors.add_error(err)
            await ctx.send(lang["bot.command.send.error.any_error"].format(err_code))
            raise err
    else:
        await ctx.send(lang["bot.command.send.error.no_connection"])


@bot.command(pass_context=True)
async def answer(ctx: Context, code):
    """Gets full answer from server using answer-code.

    Args:
        code (int): Answer code.
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if answers.__contains__(int(code)):
        answer_ = answers[int(code)]
        if len(answer_) > 1000:
            i = 0
            while(i < len(answer_)):
                if i == 0:
                    await ctx.send(lang["bot.command.answer.success.answer_page_one"].format(code, answer_[i:i+1000]))
                else:
                    await ctx.send(lang["bot.command.answer.success.answer_page"].format(int(i/1000) + 1, answer_[i:i+1000]))
                i += 1000
        else:
            await ctx.send(lang["bot.command.answer.success.answer"].format(code, answer_))
    else:
        await ctx.send(lang["bot.command.answer.error.wrong_code"])


@bot.command(pass_context=True)
async def end(ctx: Context, connection_id=None):
    """Ends ssh session.

    Args:
        connection_id (int, optional): Connection id. Defaults to None. If no produced then will be ended current session for a channel.

    Returns:
        [type]: [description]
    """
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    try:
        connection_id = channel_connections[ctx.channel.id]
    except KeyError:
        return await ctx.send(lang["bot.command.end.error.no_current_connection"])
    connection_id = int(connection_id)
    if sshs.__contains__(connection_id):
        try:
            sshs[connection_id]['conn'].close()
        except Exception as err:
            err_code = errors.add_error(err)
            await ctx.send(lang["bot.command.end.error.any_error"].format(err_code))
            raise err
        sshs.pop(connection_id)
        if channel_connections.__contains__(ctx.channel.id):
            if channel_connections[ctx.channel.id] == connection_id:
                channel_connections.pop(ctx.channel.id)
        await ctx.send(lang["bot.command.end.success.end"])
    else:
        await ctx.send(lang["bot.command.end.error.wrong_connection_id"])


@bot.command(pass_context=True)
async def disconnect(ctx: Context):
    """Disconnects from a current session. Imrortant: this action won't kill the session. Use `~end` to do it!"""
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if channel_connections.__contains__(ctx.channel.id):
        ssh_name = sshs[channel_connections[ctx.channel.id]]["connection_name"]
        channel_connections.pop(ctx.channel.id)
        await ctx.send(lang["bot.command.disconnect.success.disconnected"].format(ssh_name))
    else:
        await ctx.send(lang["bot.command.disconnect.error.no_connection"])


@bot.command(pass_context=True)
async def clist(ctx: Context):
    """Gets list of all your sessions."""
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    user_id = ctx.author.id
    user_connections = []
    for connection in sshs.sshs:
        if sshs.sshs[connection]["user_id"] == user_id:
            user_connections.append(
                {"id": connection, "connection_name": sshs.sshs[connection]["connection_name"]})
    if user_connections == []:
        await ctx.send(lang["bot.command.clist.error.no_connections"])
        return
    out = lang["bot.command.clist.message.ssh_connections"]
    for (i, dict_conn) in enumerate(user_connections):
        now = False
        if channel_connections.__contains__(ctx.channel.id):
            if channel_connections[ctx.channel.id] == dict_conn['id']:
                now = True
                if ctx.channel.type != discord.ChannelType.private:
                    out += lang["bot.command.clist.message.ssh_connection_now_channel"].format(
                        i, dict_conn["connection_name"], dict_conn["id"], ctx.channel.name)
                else:
                    out += lang["bot.command.clist.message.ssh_connection_now"].format(
                        i, dict_conn["connection_name"], dict_conn["id"])
        if not now:
            out += lang["bot.command.clist.message.ssh_connection"].format(
                i, dict_conn["connection_name"], dict_conn["id"])
    await ctx.author.send(out)
    if ctx.channel.type != discord.ChannelType.private:
        await ctx.send(lang["bot.command.clist.success.sended_to_LS"])


@bot.command(pass_context=True)
async def hamachi(ctx: Context, *args):
    """Hamachi module for bot. Read `~help` to know does it works."""
    if not roles_controller.author_has_allowed_role(ctx): 
        return await ctx.send(lang["bot.global.error.no_access_to_use"])
    if len(args) == 0:
        pass
    else:
        if args[0] == "join":
            hamachi_id = args[1]
            hamachi_password = args[2]
            cmd = ["sudo hamachi join {} {}".format(
                hamachi_id, hamachi_password)]
            result = subprocess.run("sudo hamachi join {} {}".format(
                hamachi_id, hamachi_password), shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='CP866')
            if result.stdout == 'Joining {} .. failed, invalid password\n'.format(hamachi_id):
                await ctx.send(lang["bot.command.hamachi.join.error.wrong_id_or_pass"])
            elif result.stdout == 'Joining {} .. ok\n'.format(hamachi_id):
                await ctx.send(lang["bot.command.hamachi.join.success.connected"].format(hamachi_id))
            elif result.stdout == 'Joining {} .. failed, you are already a member\n'.format(hamachi_id):
                await ctx.send(lang["bot.command.hamachi.join.error.already_connected"].format(hamachi_id))
            else:
                await ctx.send(lang["bot.command.hamachi.join.error.unknown_error"])


bot.remove_command('help')


@bot.command(pass_context=True)
async def help(ctx: Context, *args):
    if len(args) == 0:
        embed = discord.Embed(
            description=lang["bot.embed.description"], color=0xe88617)
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/app-icons/752522095296118845/236e26f1a371364e408b7621d04df5e0.png?size=128")
        embed.set_author(name=lang["bot.embed.author.name"],
                         icon_url="https://cdn.discordapp.com/app-icons/752522095296118845/236e26f1a371364e408b7621d04df5e0.png?size=64")
        embed.add_field(name=lang["bot.embed.field.commands.name"],
                        value=lang["bot.embed.field.commands.command"])
        embed.add_field(name=lang["bot.embed.field.docs.name"],
                        value=lang["bot.embed.field.docs.command"], inline=True)
        embed.add_field(name=lang["bot.embed.admin.name"],
                        value=lang["bot.embed.admin.link"])
        await ctx.send(embed=embed)
    else:
        if args[0] == "commands":
            embed = discord.Embed(
                title=lang["bot.embed.args.command.title"], color=0xe88617)
            embed.add_field(name=lang["bot.command.start.name"],
                            value=lang["bot.command.start.description"], inline=False)
            embed.add_field(name=lang["bot.command.traceback.name"],
                            value=lang["bot.command.traceback.description"], inline=False)
            embed.add_field(name=lang["bot.command.connect.name"],
                            value=lang["bot.command.connect.description"], inline=False)
            embed.add_field(name=lang["bot.command.send.name"],
                            value=lang["bot.command.send.description"], inline=False)
            embed.add_field(name=lang["bot.command.end.name"],
                            value=lang["bot.command.end.description"], inline=False)
            embed.add_field(name=lang["bot.command.disconnect.name"],
                            value=lang["bot.command.disconnect.description"], inline=False)
            embed.add_field(name=lang["bot.command.clist.name"],
                            value=lang["bot.command.clist.description"], inline=False)
            embed.add_field(name=lang["bot.command.hamachi.name"],
                            value=lang["bot.command.hamachi.description"], inline=False)
            embed.set_footer(text=lang["bot.embed.footer.commands.text"])
            await ctx.send(embed=embed)
        elif args[0] == "docs":
            embed = discord.Embed(title=lang["bot.embed.docs.field.title"],
                                  description=lang["bot.embed.docs.field.description"], color=0xe88617)
            embed.add_field(name=lang["bot.embed.docs.field.start.name"],
                            value=lang["bot.embed.docs.field.start.description"], inline=False)
            embed.add_field(name=lang["bot.embed.docs.field.main.start"],
                            value=lang["bot.embed.docs.field.main.description"])
            embed.set_footer(text=lang["bot.embed.footer.docs.text"])
            await ctx.send(embed=embed)
# @bot.event
# async def on_message(message: Message):
#     if message.channel.type == discord.ChannelType.private:
#         guild_and_channel = 'private'
#     else:
#         guild_and_channel = f'<{message.channel.guild.name}, {message.channel.name}>'
    # root_logger.log(15, f'[{message.author.name}#{message.author.discriminator} ({message.author.id})] {guild_and_channel} - {message.content}')

# logger.info('Старт бота')
event_loop = discord.Client().loop
messages_to_send = []


def get_data():
    global messages_to_send
    while(True):
        time.sleep(1)
        for discord_channel in channel_connections.connections:
            if sshs.__contains__(channel_connections.connections[discord_channel]):
                # print('Забираю инфу')
                channel: paramiko.Channel = sshs[channel_connections.connections[discord_channel]]["channel"]
                data = ''
                if channel.recv_ready():
                    recv = channel.recv(2048)
                    # print(f"Got data from server: {recv}")
                    try:
                        data += recv.decode('UTF-8')
                    except:
                        pass
                if channel.recv_stderr_ready():
                    try:
                        data += channel.recv_stderr(2048).decode('UTF-8')
                    except:
                        pass
                if data != '':
                    messages_to_send.append(
                        {"channel_id": discord_channel, "text": data})


Thread(name="data getter", target=get_data).start()


async def send_data():
    # await bot.get_channel(discord_channel).send(lang["bot.data.send.loop"].format(2048, data.decode('UTF-8')))
    global messages_to_send
    while(True):
        await asyncio.sleep(0.3)
        to_delete = []
        for message in messages_to_send:
            await bot.get_channel(message["channel_id"]).send(lang["bot.data.send.loop"].format(message["text"]))
            to_delete.append(message)
        for todel in to_delete:
            messages_to_send.remove(todel)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=f"{prefix}help"))
event_loop.create_task(send_data())
log.info("Starting program.")
bot.run(Token)
