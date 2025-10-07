import asyncio
import discord
import logging
from dotenv import load_dotenv
import os
from icalendar import Calendar, Event
import datetime as dt
import zoneinfo
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


load_dotenv()
token = os.getenv("DISCORD_TOKEN")
GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = discord.Bot(intents=intents)

icsPath = Path("./calendar.ics")
cal = Calendar.from_ical(icsPath.read_bytes())

@bot.event
async def on_ready():
    try:
        print('We have logged in as {0.user}'.format(bot))
    except Exception as e:
        print(e)

@bot.slash_command(name="sync", description="Sync events", guild=GUILD_ID)
async def sync(ctx):
    await ctx.defer()
    SYNCED = await bot.sync_commands()
    # await bot.sync_commands(guild_ids=[int(os.getenv("GUILD_ID"))])
    await bot.sync_commands()

    await ctx.respond("Synced Commands!")

async def addWeeklyEvent(ctx, startDay, length_hours, length_minutes, weeks):
    cal = Calendar.from_ical(icsPath.read_bytes())
    loop = asyncio.get_event_loop()
    currDay = startDay
    endDay = currDay + dt.timedelta(weeks=weeks, hours=length_hours, minutes=length_minutes)
    with ThreadPoolExecutor() as executor:
        for i in range(weeks):
            event = Event()
            endTime = currDay + dt.timedelta(hours=length_hours, minutes=length_minutes)
            await loop.run_in_executor(executor, event.add, 'dtstart', currDay)
            await loop.run_in_executor(executor, event.add, 'dtend', endTime)
            await loop.run_in_executor(executor, event.add, 'summary', f"{ctx.author.id}, {ctx.author.name}")
            await loop.run_in_executor(executor, cal.add_component, event)

            currDay += dt.timedelta(weeks=1)

        with open("./calendar.ics", 'wb') as f:
            f.write(cal.to_ical())

    await ctx.respond(f"Added {weeks} events starting from {startDay.strftime('%b %d %a %I:%M %p')} to {endDay.strftime('%b %d %a %I:%M %p')}")

@bot.slash_command(name="addweeklyevent", description="Adds office hours to calendar", guild=GUILD_ID)
@discord.option("start_day", type=int, required=True, min_value=1, max_value=31)
@discord.option("start_month", type=int, required=True, min_value=1, max_value=12)
@discord.option("start_year", type=int, required=True, min_value=0, max_value=9999)
@discord.option("start_hour", type=int, required=True, min_value=1, max_value=12)
@discord.option("start_minute", type=int, required=True, min_value=0, max_value=59)
@discord.option("start_pm", type=bool, description="True = PM, False = AM", required=True)
@discord.option("end_day", type=int, required=True, min_value=1, max_value=31)
@discord.option("end_month", type=int, required=True, min_value=1, max_value=12)
@discord.option("end_year", type=int, required=True, min_value=0, max_value=9999)
@discord.option("weeks", type=int, required=True, min_value=0, description="The amount of weeks this event will reoccur")
@discord.option("length_hours", type=int, required=True, min_value=0)
@discord.option("length_minutes", type=int, required=True, min_value=0)
async def addweeklyevent(ctx: discord.ApplicationContext, start_day: int, start_month: int, start_year: int, start_hour: int,
                         start_minute: int, start_pm: bool, length_hours: int, length_minutes: int, weeks: int):
    try:
        currDay = dt.datetime(start_year, start_month, start_day, start_hour + (int(start_pm) * 12), start_minute, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    except Exception as e:
        print("Invalid parameters for time given. Make sure all parameters allow for valid times. Perhaps the given day is not in this month?")

    await ctx.defer()

    await addWeeklyEvent(ctx, currDay, length_hours, length_minutes, weeks)

def startOfWeek(date: dt.datetime) -> dt.datetime:
    dayOfWeek = date.weekday()
    diff = (7 + (dayOfWeek - 6)) % 7
    return date + dt.timedelta(days=-1 * diff)

@bot.slash_command(name="getoffcehours", description="shows the office hours of a specific user", guild=GUILD_ID)
@discord.option("weeks", type=int, required=True, min_value=1, description="The amount of weeks starting from this current week that the bot will show office hours for")
async def getoffcehours(ctx: discord.ApplicationContext, user: discord.User, weeks: int):
    date = dt.datetime(dt.datetime.now().year, dt.datetime.now().month, dt.datetime.now().day,
                       0, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    cal = Calendar.from_ical(icsPath.read_bytes())
    thisWeek = startOfWeek(date)
    currDay = thisWeek

    eventTimes = f"{user.name}'s office hours for this week:\n"

    for event in cal.walk("VEVENT"):
        if (event.get("dtstart").dt >= thisWeek and event.get("dtstart").dt < (thisWeek + dt.timedelta(weeks=weeks))
                and str(user.id) in event.get("SUMMARY")):
            eventTimes += event.get("dtstart").dt.strftime('%b %d %a %I:%M %p') + "\n"

    if(eventTimes == f"{user.name}'s office hours for this week:\n"):
        eventTimes += "None"

    await ctx.respond(eventTimes)

def makeNewCalendar() -> Calendar:
    new = Calendar()
    new.add("prodid", "-//Office Hours//discord//EN")
    new.add("version", "1.0")
    new.add("summary", "Office Hours")
    return new

@bot.slash_command(name="editofficehours", description="Edits the date and time of your office hours for a given day of the week", guild=GUILD_ID)
@discord.option("start_day", type=int, required=True, min_value=1, max_value=31)
@discord.option("start_month", type=int, required=True, min_value=1, max_value=12)
@discord.option("start_year", type=int, required=True, min_value=0)
@discord.option("start_hour", type=int, required=True, min_value=1, max_value=12)
@discord.option("start_minute", type=int, required=True, min_value=0, max_value=59)
@discord.option("start_pm", type=bool, description="True = PM, False = AM", required=True)
@discord.option("new_day", type=int, required=True, min_value=1, max_value=31)
@discord.option("new_month", type=int, required=True, min_value=1, max_value=12)
@discord.option("new_year", type=int, required=True, min_value=0)
@discord.option("new_start_hour", type=int, required=True, min_value=1, max_value=12)
@discord.option("new_start_minute", type=int, required=True, min_value=0, max_value=59)
@discord.option("new_length_hours", type=int, required=True, min_value=0)
@discord.option("new_length_minutes", type=int, required=True, min_value=0)
@discord.option("new_pm", type=bool, required=True, description="True = PM, False = AM")
@discord.option("weeks", type=int, required=True, min_value=0, description="The amount of weeks this event will reoccur")
async def editevents(ctx: discord.ApplicationContext,  start_day: int, start_month: int, start_year: int,
                    start_hour: int, start_minute: int, start_pm: bool, new_day: int, new_month: int, new_year: int, new_start_hour: int, new_start_minute: int, new_pm: bool,
                     new_length_hours: int, new_length_minutes: int, weeks: int):
    await ctx.defer()
    temp = makeNewCalendar()

    result = f"Changed the following office hours:\n"


    start = dt.datetime(start_year, start_month, start_day, start_hour + (12 * int(start_pm)), start_minute, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    cal = Calendar.from_ical(icsPath.read_bytes())
    delta = (dt.datetime(new_year, new_month, new_day, new_start_hour + (12 * int(new_pm)), new_start_minute, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
             - start).total_seconds()

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        for event in cal.walk("VEVENT"):
            eventTime = event.get("dtstart").dt
            if (start <= eventTime < (start + dt.timedelta(weeks=weeks))
                    and str(ctx.author.id) in event.get("SUMMARY") and eventTime.hour == start.hour
                    and eventTime.minute == start.minute and eventTime.weekday() == start.weekday()):
                startTime = event.get("dtstart").dt + dt.timedelta(seconds=delta)
                endTime = startTime + dt.timedelta(hours=new_length_hours, minutes=new_length_minutes)

                e = Event()
                await loop.run_in_executor(executor, e.add, 'dtstart', startTime)
                await loop.run_in_executor(executor, e.add, 'dtend', endTime)
                await loop.run_in_executor(executor, e.add, 'summary', event.get("SUMMARY"))
                await loop.run_in_executor(executor, temp.add_component, e)

                result += f"{(startTime - dt.timedelta(seconds=delta)).strftime('%b %d %a %I:%M %p')} was changed to {startTime.strftime('%b %d %a %I:%M %p')}\n"

            else:
                await loop.run_in_executor(executor, temp.add_component, event)

        with open("./calendar.ics", 'wb') as new:
            new.write(temp.to_ical())

    if result == f"Changed the following office hours:\n":
        result += "None"

    await ctx.respond(result)

@bot.slash_command(name="deleteofficehours", description="removes office hours at a specific time for a given amount of weeks", guild=GUILD_ID)
@discord.option("day", type=int, required=True, min_value=1, max_value=31)
@discord.option("month", type=int, required=True, min_value=1, max_value=12)
@discord.option("year", type=int, required=True, min_value=0)
@discord.option("hour", type=int, required=True, min_value=1, max_value=12)
@discord.option("minute", type=int, required=True, min_value=0, max_value=59)
@discord.option("pm", type=bool, description="True = PM, False = AM", required=True)
@discord.option("weeks", type=int, required=True, min_value=0, description="The amount of weeks this event will reoccur")
async def deleteHours(ctx: discord.ApplicationContext, day: int, month: int, year: int, hour: int, minute: int, pm: bool, weeks: int):
    await ctx.defer()
    temp = makeNewCalendar()

    result = f"Deleted the following office hours:\n"

    start = dt.datetime(year, month, day, hour + (12 * int(pm)), minute, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    cal = Calendar.from_ical(icsPath.read_bytes())

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        for event in cal.walk("VEVENT"):
            eventTime = event.get("dtstart").dt
            if (start <= eventTime < (start + dt.timedelta(weeks=weeks))
                    and str(ctx.author.id) in event.get("SUMMARY") and eventTime.hour == start.hour
                    and eventTime.minute == start.minute and eventTime.weekday() == start.weekday()):
                result += f"Removed office hours at {eventTime.strftime('%b %d %a %I:%M %p')}\n"
            else:
                await loop.run_in_executor(executor, temp.add_component, event)

        with open("./calendar.ics", 'wb') as new:
            new.write(temp.to_ical())

    if result == f"Deleted the following office hours:\n":
        result += "None"

    await ctx.respond(result)

bot.run(token)
