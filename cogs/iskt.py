import discord
import json
import time
import mysql.connector as mdb
from discord.ext import commands
from enum import Enum

class DBMApper:
    def __init__(self, host, port, database, login, password):
        self.host = host
        self.port = port
        self.port = port
        self.database = database
        self.login = login
        self.password = password
        self.con = None

    def getConnection(self):
        if self.con is None:
            self.con = mdb.connect(host=self.host, port=self.port,db=self.database, user=self.login, passwd=self.password)
        return self.con


    def executeQuery(self, query, *args):
        
        try:
            db = self.getConnection()            
            cur = db.cursor()
            cur.execute(query, args)
            
            db.commit()

            return cur
        except mdb.Error as e:
            print("Error : " + str(e))

    def select(self, query, *args):
        try:
            db = self.getConnection()            
            cur = db.cursor()
            cur.execute(query, args)
            
            return cur
        except mdb.Error as e:
            print("Error : " + str(e))

class Region(Enum):
    ANY = 0
    EU  = 1
    OC  = 2
    NA  = 3

    @staticmethod
    def getRegion(member : discord.Member):
        roles = [r.name for r in member.roles]

        if 'EU' in roles:
            return Region.EU
        elif 'OC' in roles:
            return Region.OC
        elif 'NA' in roles:
            return Region.NA
        else:
            return Region.ANY
    
    # Will return true if a == ANY
    @staticmethod
    def compareTo(a, b):
        return a == Region.ANY or a == b


class ISKT:
    # SQL queries
    QUERY_SELECT_MEMBER_BY_D_ID = "SELECT * FROM Members WHERE discordID = %s;"
    QUERY_UPDATE_MEMBER_BY_D_ID = "UPDATE Members SET steamID = %s, streamURL = %s WHERE discordID = %s;"
    QUERY_INSERT_MEMBER_BY_D_ID = "INSERT INTO Members VALUES (%s, %s, %s);"
    
    CFG_PATH = "cogs/iskt_config.json"
    

    def __init__(self, bot):
        self.bot = bot
        self.loadConfig()
        self.db = DBMApper(self.config['db-host'], self.config['db-port'], self.config['db-database'], self.config['db-login'], self.config['db-password'])

    @classmethod
    def loadConfig(self):
        file = open(self.CFG_PATH, 'r')
        raw = file.read()
        config = json.loads(raw)
        self.config = config


    @commands.command(pass_context=True, no_pm=True)
    async def canRead(self, ctx, chan : discord.Channel = None):
        """Shows members who can access a channel"""
        result = ""
        server = ctx.message.server
        
        if chan is None: # Is there an argument ? XXX Since the argument has now a type this shouldn't happen.
            result += "No given channel, using channel used to send the command.\n"
            channel = ctx.message.channel
        else:
            channel = server.get_channel(chan.id)
            if channel is None: # Does this channel exists ?
                result += "Can't find this channel, using channel used to send the command.\n"
                channel = ctx.message.channel

        members = server.members # Every members of the server. TODO there might be a way to only get users that has a role.

        result += "**__List of users who can access " + channel.mention + " : __**\n"

        resultList = list()
        

        for m in members:
            if channel.permissions_for(m).read_messages :
                tmp = ""
                if m.nick is not None: # Add server nickname first 
                    tmp += m.nick + " : " 
                tmp += m.name + "\n"
                resultList.append(tmp)

        resultList.sort() # Sort result 

        for e in resultList:
            result += e

        await self.bot.say(result)
        

    @commands.command(pass_context=True, no_pm=True)
    async def testLog(self, ctx, toLog : str):
        await self.log(toLog, ctx.message.server)

    @commands.command(pass_context=True, no_pm=True)
    async def add(self, ctx, member : discord.Member, channel : discord.Channel = None):
        """Adds a "read_permissions" overwrite to a channel """
        await self.changeCanRead(ctx, member, channel, True)

    @commands.command(pass_context=True, no_pm=True)
    async def remove(self, ctx, member : discord.Member, channel : discord.Channel = None): 
        """Removes a "read_permissions" overwrite to a channel """
        await self.changeCanRead(ctx, member, channel, False)        

    @commands.command()
    async def setSteamID(self, user : discord.User, steamID : str):
        """Links a Steam ID to an User."""
        self.updateUserInDB(user, steamID, "")
        await self.bot.say("Done.")

    @commands.command()
    async def setStreamURL(self, user : discord.User, streamURL : str):
        """Links a stream URL to an User."""
        self.updateUserInDB(user, "", streamURL)
        await self.bot.say("Done.")

    @commands.command()
    async def setInfo(self, user : discord.User, steamID : str = "",  streamURL : str = ""):
        """Links a Steam ID and a stream URL to an User."""
        self.updateUserInDB(user, steamID, streamURL)
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    async def refreshDirectories(self, ctx):
        await self.refreshStaffDirectory(ctx.message.server, True)
        await self.bot.say("Done.")

    async def changeCanRead(self, ctx, member : discord.Member, channel : discord.Channel, newRule : bool):
        if channel is None:
            channel = ctx.message.channel
        
        permission = discord.PermissionOverwrite()
        permission.update(read_messages = newRule)
        await self.bot.edit_channel_permissions(channel, member, permission)
        await self.bot.say(ctx.message.author.mention + " done.")


    async def matchChannelNotifier(self, before : discord.Channel, after : discord.Channel):
        before_canRead = list(filter((lambda e: e[1].read_messages), before.overwrites))
        before_cannotRead = list(filter((lambda e: not e[1].read_messages), before.overwrites))

        after_canRead = list(filter((lambda e: e[1].read_messages), after.overwrites))
        after_cannotRead = list(filter((lambda e: not e[1].read_messages), after.overwrites))

        updates = list()
        
        for t in before_canRead:
            if not ISKT.hasKey(after_canRead, t[0]):
                updates.append(t)
        for t in before_cannotRead:
            if not ISKT.hasKey(after_cannotRead, t[0]):
                updates.append(t)        

        for t in updates:
            if isinstance(t[0], discord.Member):
                await self.introduce(t[0], after, not t[1].read_messages) # 'not' because I used before instead of after. 
            elif isinstance(t[0], discord.Role):
                await self.introduce(t[0], after, not t[1].read_messages) 
            else:
                print("Shouldn't happen. " + str(t))
        
        return None


    async def on_member_update(self, before : discord.Member, after : discord.Member):
        await self.checkRolesAndUpdateDirectories(before, after)
    
    async def on_channel_update(self, before : discord.Channel, after : discord.Channel):
        if ISKT.isMatchChannel(before):
            await self.matchChannelNotifier(before, after)

    #roles = [r.name for r in m.roles]
    async def checkRolesAndUpdateDirectories(self, before : discord.Member, after : discord.Member):
        before_roles = [r.name for r in before.roles]
        after_roles = [r.name for r in after.roles] 

        roleChanges = list(filter(lambda r: r not in after_roles, before_roles)) + list(filter(lambda r: r not in before_roles, after_roles))

        for r in roleChanges:
            if r in self.config['staff-roles']:
                await self.refreshStaffDirectory(before.server, False)
                break
        
    # Send a message to a channel concerning permissions.
    # isAWelcome = welcome
    # !isAWelcome = goodbye
    async def introduce(self, e, channel : discord.Channel, isAWelcome : bool):
        if isinstance(e, discord.Role): # Role
            prefix = ":regional_indicator_r: "
        elif isinstance(e, discord.Member): # User
            prefix = ":regional_indicator_m: "
        else: # Other
            prefix = ":regional_indicator_o: "

        if isAWelcome:
            message = prefix + ":green_heart: " + e.mention + " has now access to this channel."
        else: 
            message = prefix + ":red_circle: " + e.mention + " cannot access this channel anymore." 

        await self.bot.send_message(channel, message)

    # Log a str in the default log channel. Will simply print if the log channel can't be found.
    async def log(self, log : str, server : discord.Server):
        logChannel = ISKT.getChannelByName(self.config['LOG_CHANNEL'], server)

        if logChannel is None:
            print("Can't find log channel for " + server.name + ".")
            print(log)
        else:
            await self.bot.send_message(logChannel, log)


    async def refreshStaffDirectory(self, server : discord.Server, isForced : bool):
        chan = ISKT.getChannelByName(self.config['staff-directory'], server)
        if chan is None or not (chan.type == discord.ChannelType.text):
            await self.log("Can't find channel " + self.config['staff-directory'] + " or the channel is not a text one.", server)
        else: 
            members = server.members
            directory = self.getStaffDirectory(members)
            directory.append("--\nLast update : " + time.ctime() + "\nForced update : " + str(isForced)) 
            hasMessage = False
            i = 0
            messages = list()

            async for m in self.bot.logs_from(chan, limit=10):
                messages.append(m)

            messages.sort(key=lambda m : m.timestamp)

            for m in messages:     
                hasMessage = True
                if i < len(directory):
                    await self.bot.edit_message(m, directory[i])
                else:
                    await self.bot.delete_message(m)
                i += 1

            if not hasMessage:
                for d in directory:
                    await self.bot.send_message(chan, d)

            if hasMessage and i < len(directory):
                for j in range(i, len(directory)):
                    await self.bot.send_message(chan, directory[j])


    def getStaffDirectory(self, members):
        returnValue = list()
        result = "__**ISKT 2 Staff**__\n\n\n"
        # Managers
        result += "**Tournament Managers:**\n"
        result += self.getMemberListByRole(members, 'Tournament Manager', False, False) + "\n\n"
        # Officials
        result += "**Officials:**\n"
        result += self.getMemberListByRole(members, 'Official', False, False) + "\n\n"
        # Lead Caster
        result += "**Lead Caster:**\n"
        result += self.getMemberListByRole(members, 'Lead Caster', False, False) + "\n\n"
        # Developers
        result += "**Developers:**\n"
        result += self.getMemberListByRole(members, 'Developer', False, False) + "\n\n"
        # Adviser
        # XXX No adviser role it seems.

        returnValue.append(result) # Lets hope python's string aren't mutable :^)
        result = ""
        # Streamers
        result += "__**OFFICIAL ISKT 2 CASTERS**__\n\n\n"
        result += "**EU-based**\n"
        result += self.getMemberListByRole(members, 'Caster', True, True, Region.EU) + "\n\n"
        result += "**NA-based**\n"
        result += self.getMemberListByRole(members, 'Caster', True, True, Region.NA) + "\n\n"
        result += "**OC-based**\n"
        result += self.getMemberListByRole(members, 'Caster', True, True, Region.OC) + "\n\n"

        returnValue.append(result) 
        result = ""

        result += "__**OFFICIAL ISKT 2 REFEREES**__\n\n\n"
        result += "**EU-based**\n"
        result += self.getMemberListByRole(members, 'EU Referee', True, False) + "\n\n"
        result += "**NA-based**\n"
        result += self.getMemberListByRole(members, 'NA Referee', True, False) + "\n\n"
        result += "**OC-based**\n"
        result += self.getMemberListByRole(members, 'AU Referee', True, False) + "\n\n"
        
        returnValue.append(result) # Lets hope python's string aren't mutable :^)
        
        return returnValue

    def updateUserInDB(self, user : discord.User, steamID = "", streamURL = ""):
        dbUser = self.getUser(user)

        if dbUser is not None:
            if steamID == "" or streamURL == "":
                if steamID == "":
                    steamID = dbUser[0]
                if streamURL == "":
                    streamURL == dbUser[1]

            self.updateUser(user, steamID, streamURL)
        else:
            self.insertUser(user, steamID, streamURL)

    def insertUser(self, user : discord.User, steamID = "", streamURL = ""):
        self.db.executeQuery(self.QUERY_INSERT_MEMBER_BY_D_ID, user.id, steamID, streamURL)
    
    def updateUser(self, user : discord.User, steamID = "", streamURL = ""):
        # Make sure we don't overwrite data. Not used but I prefer not to lose data.
        if steamID == "" or streamURL == "":
            info = self.getUser(user)
            if info is not None:
                if steamID == "":
                    steamID = info[0]
                if streamURL == "":
                    streamURL == info[1]

        self.db.executeQuery(self.QUERY_UPDATE_MEMBER_BY_D_ID, steamID, streamURL, user.id)
    
    def getUser(self, user : discord.User):
        cur = self.db.select(self.QUERY_SELECT_MEMBER_BY_D_ID, user.id)
        if cur is None:
            print("cur is none")
            return None
        
        row = cur.fetchone()

        if row is None: # No result
            return None

        return (row[1], row[2])

    def getMemberListByRole(self, members : list, role : str, showSteamID : bool, showStreamURL : bool, region : Region = Region.ANY):
        result = ""

        filteredMembers = list(filter((lambda m : ISKT.hasRole(m, role) and Region.compareTo(region, Region.getRegion(m))), members))

        for m in filteredMembers:
            result += "- " + m.mention
            if showSteamID or showStreamURL:
                userData = self.getUser(m)
                if showSteamID:
                    result += " : " + (" no data" if userData is None or userData[0] == "" else userData[0])
                if showStreamURL:
                    result += " : " + (" no data" if userData is None or userData[1] == "" else userData[1])
            result += "\n"

        return result

    # Gets a channel using its name. Returns None when there's no result.
    @staticmethod
    def getChannelByName(name : str, server : discord.Server):
        for c in server.channels: # TODO there must be a kind of list.get(str) in python to simplify this function.
            if c.name == name:
                return c
        return None

    # a/b
    @staticmethod
    def dif(a : list, b : list):
        return list(set(a) - set(b))

    @staticmethod
    def isMatchChannel(channel : discord.Channel):
        n = channel.name
        return n[0].isalpha() and n[1].isdigit() and n[2] == '_' # Too lazy to learn how regex work in python
    
    @staticmethod
    def hasKey(tupleList, key):
        for t in tupleList:
            if t[0] == key:
                return True
        return False

    @staticmethod
    def hasRole(member : discord.Member, role : discord.Role):
        roles = [r.name for r in member.roles]
        return role in roles


def setup(bot):
    iskt = ISKT(bot)

    bot.add_cog(iskt)
