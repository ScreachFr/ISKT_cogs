import discord
from discord.ext import commands

class ISKT:
    LOG_CHANNEL = "bot_admin"


    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def canRead(self, ctx, chan : discord.Channel = None):
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
                tmp += m.name + "#" + m.discriminator + "\n"
                resultList.append(tmp)

        resultList.sort() # Sort result 

        for e in resultList:
            result += e

        await self.bot.say(result)

    @commands.command(pass_context=True, no_pm=True)
    async def testLog(self, ctx, toLog : str):
        await self.log(toLog, ctx.message.server)


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
        pass
    
    async def on_channel_update(self, before : discord.Channel, after : discord.Channel):
        if ISKT.isMatchChannel(before):
            await self.matchChannelNotifier(before, after)


    # Send a message to a channel concerning permissions.
    # isAWelcome = welcome
    # !isAWelcome = goodbye
    async def introduce(self, e, channel : discord.Channel, isAWelcome : bool):
        if isAWelcome:
            message = e.mention + " has now access to this channel."
        else: 
           message = e.mention + " cannot access this channel anymore." 

        await self.bot.send_message(channel, message)

    # Log a str in the default log channel. Will simply print if the log channel can't be found.
    async def log(self, log : str, server : discord.Server):
        logChannel = ISKT.getChannelByName(self.LOG_CHANNEL, server)

        if logChannel is None:
            print("Can't find log channel for " + server.name + ".")
            print(log)
        else:
            await self.bot.send_message(logChannel, log)

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

def setup(bot):
    bot.add_cog(ISKT(bot))

