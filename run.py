import discord
import discord.utils as dutil
import os
import numpy as np
import pickle
import atexit
import argparse
from random import choice
from dataclasses import dataclass

BUYINAMT = 1000
PREFIX = '~'
ADMINS = [
	'CobaltAlchemist#1029',
	'Danté#2385'
]

@dataclass
class Player:
	username: str
	balance: int = 0
	voted: bool = False
	boughtin: int = 0
	vote: str = ""
	voteamt: int = 0

client = discord.Client(activity=discord.Game(name="~help"))

class Database:
	def __init__(self, file):
		self.filename = file
		if os.path.exists(self.filename):
			with open(self.filename, 'rb') as f:
				self.players = pickle.load(f)
		else:
			self.players = []
		self.open_event()
		self.eventmsg = None
		
	def open_event(self, amount = BUYINAMT):
		didntvote = []
		for p in self.players:
			if not p.voted and p.boughtin:
				p.balance -= p.boughtin
				didntvote.append(p)
			p.voted = False
			p.vote = ""
			p.balance += p.voteamt
			p.voteamt = 0
			p.boughtin = 0
		with open(self.filename, 'wb') as f:
			pickle.dump(self.players, f)
		return didntvote
			
	def _get_player(self, player):
		for p in self.players:
			if player == p.username:
				return p
		p = Player(player)
		self.players.append(p)
		return p
			
	def buy_in(self, player, amount = BUYINAMT):
		p = self._get_player(player)
		if p.boughtin:
			return False
		p.boughtin = amount
		p.balance += amount
		return p
	
	def make_vote(self, player, vote, amt):
		if not isinstance(amt, int):
			amt = int(amt)
		p = self._get_player(player)
		if p.vote != "" and p.vote != vote:
			p.balance += p.voteamt
			p.voteamt = 0
			p.vote = ""
			if p.balance >= amt:
				p.voted = True
		if p.balance < amt:
			return p, False
		p.voted = True
		p.vote = vote
		p.voteamt += amt
		p.balance -= amt
		return p, True
	
	def declare_result_old(self, result):
		winners = []
		pool = 0
		winpool = 0
		for p in self.players:
			if p.vote == result:
				winners.append(p)
				winpool += p.voteamt
			else:
				p.voteamt = 0
			pool += p.voteamt
			p.vote = ""
		if len(winners) == 0:
			return [], 0
		for p in winners:
			p.balance += int(pool * (p.voteamt / winpool))
			p.voteamt = 0
		return winners, pool
	
	def declare_result(self, result):
		winners = []
		pool = sum([p.voteamt for p in self.players])
		for p in self.players:
			if p.vote == result:
				print(f"Pool percentage: {(p.voteamt / pool)}")
				print(f"Vote Amt: {p.voteamt}")
				print(f"{p.balance} += {int(p.voteamt + p.voteamt * (p.voteamt / pool))}")
				p.balance += int(p.voteamt + p.voteamt * (p.voteamt / pool))
				winners.append(p)
			p.voteamt = 0
			pool += p.voteamt
			p.vote = ""
		if len(winners) == 0:
			return [], 0
		return winners, pool
		
	def reset(self):
		self.open_event()
		for p in self.players:
			p.balance = 0

servers = {}

def get_server(server):
	try:
		return servers[server]
	except KeyError:
		db = Database(f'{server}.pkl')
		servers[server] = db
		return db
		
deathchoices = [
	'It was a kill!',
	'They were killed!',
	'They didn\'t survive!',
	'They got destroyed!',
	'RIP them',
]

lifechoices = [
	'They survived!',
	'They lived!',
	'They got through it!',
	'Of course they lived.',
	'So close!',
]

@client.event
async def on_ready():
	print('We have logged in as {0.user}'.format(client))
	
@client.event
async def on_message(message):
	if message.author == client.user:
		return
	if message.author.bot:
		return
	if len(message.content) == 0:
		return
	
	server = str(message.guild)
	player = str(message.author)
	
	s = message.content.split()
	if len(s) == 0:
		return
	command = s[0].lower()
	if len(s) > 1:
		args = s[1:]
	else:
		args = []
		
	db = get_server(server)
	
	print(server, player, s)
	
	if command == PREFIX + "help":
		await message.channel.send('\n'.join([
			"Available Commands",
			PREFIX + "open - opens a new event (Admin only)",
			PREFIX + "death - resolve the round as a death (Admin only)",
			PREFIX + "life - resolve the round as alive (Admin only)",
			PREFIX + "dead # - bet for dead",
			PREFIX + "alive # - bet for alive",
			PREFIX + "balance - see balances for all participating members",
			PREFIX + "cashout - reset everything (Admin only)",
			]))
	
	if db.eventmsg is None and command != PREFIX + "open" and command != PREFIX + "balance" and command != PREFIX + "dev" and command != PREFIX + "cashout":
		return
		
	if command == PREFIX + "open":
		if player not in ADMINS:
			return
		players = db.open_event()
		players = ', '.join([p.username for p in players])
		if len(players) > 0:
			db.eventmsg = await message.channel.send(f"Opening new event! React to this to buy in. Sorry {players}. You failed to vote and lost your last buy in")
		else:
			db.eventmsg = await message.channel.send(f"Opening new event! React to this to buy in.")
		print(db.eventmsg)
	elif command == PREFIX + "death":
		if player not in ADMINS:
			return
		winners, reward = db.declare_result('death')
		await message.channel.send(f"{choice(deathchoices)} Distributing {reward} to {len(winners)} players")
	elif command == PREFIX + "life":
		if player not in ADMINS:
			return
		winners, reward = db.declare_result('life')
		await message.channel.send(f"{choice(lifechoices)} Distributing {reward} to {len(winners)} players")
	elif command == PREFIX + "dead":
		if len(args) != 1:
			await message.channel.send("You gotta input an amount my guy: " + PREFIX + "Dead #")
		else:
			amt = args[0]
			p, res = db.make_vote(player, 'death', amt)
			if res:
				await message.channel.send(f"Added bet, you have {p.balance} left, your current bet is {p.vote} for {p.voteamt}")
			else:
				await message.channel.send(f"Not enough cash, you only have {p.balance}")
	elif command == PREFIX + "alive":
		if len(args) != 1:
			await message.channel.send("You gotta input an amount my guy: " + PREFIX + "Alive #")
		else:
			amt = args[0]
			p, res = db.make_vote(player, 'life', amt)
			if res:
				await message.channel.send(f"Added bet, you have {p.balance} left, your current bet is {p.vote} for {p.voteamt}")
			else:
				await message.channel.send(f"Not enough cash, you only have {p.balance}")
	elif command == PREFIX + "balance":
		pstrs = [f"{p.username}: {p.balance}" for p in db.players]
		await message.channel.send("Players on this server:\n" + '\n'.join(pstrs))
	elif command == PREFIX + "cashout":
		if player not in ADMINS:
			return
		db.reset()
		db.eventmsg = None
	elif command == PREFIX + "dev":
		await message.channel.send(str(db.players))
		
@client.event
async def on_reaction_add(reaction, user):
	message = reaction.message
	if message.author != client.user:
		return
		
	server = str(message.guild)
	player = str(user)
	
	db = get_server(server)
	
	if db.eventmsg.id == message.id:
		p = db.buy_in(player)
		print(server, player, message.id, p)
		
@atexit.register
def save_dbs():
	for db in servers.values():
		db.open_event()

if __name__=="__main__":
	parser = argparse.ArgumentParser(description='Gamble bot runner')
	parser.add_argument('-k', '--key', help='API Key', default=None)
	parser.add_argument('--gpu', action='store_true')
	args = parser.parse_args()
	#Permossions: 68608
	#https://discord.com/api/oauth2/authorize?client_id=883520676735094805&permissions=68608&scope=bot%20applications.commands
	client.run(args.key)