from debug import pprint

pprint("raw", conversion="str")
pprint(["quotes"], conversion="str")

pprint("raw", conversion="auto")
pprint(["quotes"], conversion="auto")

pprint("quotes", conversion="repr")
pprint(["quotes"], conversion="repr")
