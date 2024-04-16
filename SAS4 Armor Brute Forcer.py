#!/usr/bin/env python
# coding: utf-8

# In[ ]:


try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError:
    input("Pandas library is not installed. Please install so this program can run.")
    raise SystemExit

import itertools as it
from time import perf_counter

try:
    path = "Armor stats.xlsx" 
    MastCol = pd.io.excel.read_excel(path, sheet_name="Mastery and Collection")
    MastCol.set_index(["Resistance", "Armor Type"], inplace = True)
    MastCol.loc[:,"Mastery 0":"Mastery 5"] = MastCol.loc[:,"Mastery 0":"Mastery 5"].cumsum(axis = 1)
    Armors = pd.io.excel.read_excel(path, sheet_name="Armor Values").fillna(0)
    Augs = pd.io.excel.read_excel(path, sheet_name="Aug Multiplier")
    Adder = pd.io.excel.read_excel(path, sheet_name="Item Type Adder")
except ImportError:
    input("openpyxl library (optional dependancy of pandas) is not installed. Please install so this program can run.")
    raise SystemExit


try:
    bonusList = pd.read_csv('BonusCombos.csv')
    bonusList = bonusList.set_index("Unnamed: 0").to_dict()
except FileNotFoundError:
    bonusList = {}

try:
    armorList = pd.read_csv('ArmorCombos.csv')
    armorList = armorList.set_index("Unnamed: 0")
    armorList = dict(pd.DataFrame(armorList))
    armorList = {i:j.dropna() for i, j in armorList.items()}
except FileNotFoundError:
    armorList = {}


def isInt(s):
    try:
        v = int(s)
        return v
    except ValueError:
        return False


def isFloat(s):
    try:
        v = float(s)
        return v
    except ValueError:
        return False    

    
def takeInput(question, acceptedFormats = [], acceptedRange = [-9999, 9999]):
    while True:
        ans = input(question)
        if ans == "e":
            return ans
        if len(acceptedFormats) == 0:
            return ans
        for f in acceptedFormats:
            j  = f(ans)
            if not j is False:
                if not acceptedRange or acceptedRange[0] <= j <= acceptedRange[1]:
                    return j
        print ("Invalid input. Try again.")


class ArmorSolverInput:
    def __init__(self):
        self.BAE = 0
        self.Helm = ""
        self.Vest = ""
        self.Gloves = ""
        self.Pants = ""
        self.Boots = ""
        self.Masteries = [0,0,0,0,0]
        self.Collections = {"Std":[0,0,0,0,0], "Red":[0,0,0,0,0], "Bck":[0,0,0,0,0]}
        self.BaseCores = [0, 0, 0, 0, 0]
        self.Augs = [[0,0,0],
                     [0,0,0],
                     [0,0,0],
                     [0,0,0],
                     [0,0,0]
                    ]
class ArmorInput:
    def __init__(self, BAE = 0, Armor = [""], Masteries = 0, BaseCores = 0, Collections = {"Std":0, "Red":0, "Bck":0}, Augs = [0,0,0]):
        self.BAE = BAE
        self.Armor = pd.DataFrame(Armor)
        self.Armor.columns = ["ArmorName"]
        self.Armor = self.Armor["ArmorName"]
        self.Masteries = Masteries
        self.BaseCores = BaseCores
        self.Collections = Collections
        self.Augs = Augs

def Resistances(Entry):
    CalcArmors = pd.DataFrame(Entry.Armor).merge(Armors[["ArmorName", "ArmorType", "Physical", "Thermal", "Toxic"]], how="left")
    CalcArmors = CalcArmors.merge(Adder, how="left")
    Multipliers = np.array([Augs.loc[Entry.Augs[0], "Fort Mult"], Augs.loc[Entry.Augs[1], "Heat Mult"], Augs.loc[Entry.Augs[2], "Hazc Mult"]])
    CalcArmors[["Physical", "Thermal", "Toxic"]] *= 1 + Multipliers + 0.05 * Entry.BaseCores
    CalcArmors[["Physical", "Thermal", "Toxic"]] += np.array(CalcArmors["Adder"])[None].T * Entry.Augs
    CalcArmors[["Physical", "Thermal", "Toxic"]] *= 1 + 0.07 * Entry.BAE
    CalcArmors[["Physical", "Thermal", "Toxic"]] = CalcArmors[["Physical", "Thermal", "Toxic"]].round(3)
    CalcArmors = CalcArmors.melt(id_vars = ["ArmorName", "ArmorType"], value_vars = ["Physical", "Thermal", "Toxic"])
    CalcArmors = CalcArmors.merge(MastCol.T.iloc[Entry.Masteries].rename("MasteryBonus"), left_on = ["ArmorType", "variable"], right_on = ["Armor Type", "Resistance"], how = "left")
    CollectionsCalc = (MastCol.loc[:,"Standard":"Black"] * Entry.Collections).sum(axis = 1).rename("CollectionBonus")
    CalcArmors = CalcArmors.merge(CollectionsCalc, left_on = ["ArmorType", "variable"], right_on = ["Armor Type", "Resistance"], how = "left")
    CalcArmors["value"] += CalcArmors["MasteryBonus"] + CalcArmors["CollectionBonus"]
    CalcArmors = CalcArmors.pivot_table(index = ["ArmorName", "ArmorType"], columns = "variable", values = "value", sort=False)
    CalcArmors.columns.name = None
    CalcArmors = CalcArmors.reset_index()
    return CalcArmors
    

def calcResistances(Entry):
    Entry.Augs = [12, 12, 12]
    DataRes = Resistances(Entry)
    Entry.Augs = [0, 0, 0]
    DataBaseRes = Resistances(Entry)
    DataRes.merge(DataBaseRes)
    DataCombRes = (pd.concat([DataRes.set_index(["ArmorName", "ArmorType"]), 
                     DataBaseRes.set_index(["ArmorName", "ArmorType"])], 
                    axis=1, 
                    keys=[1, 0])
          .swaplevel(0, 1, axis=1)
                  )
    
    DataCombRes = DataCombRes.rename(columns={"Physical": 0, "Thermal": 1, "Toxic": 2}, level=0)
    return DataCombRes


def permuteOptimise(Entry, ArmorAugSlots, includeRes = False, includeAugCombos = False):
    DataCombRes = calcResistances(Entry)
    
    ArmorGroup = DataCombRes.reset_index()[["ArmorName", "ArmorType"]]
    ArmorGroup = ArmorGroup.groupby("ArmorType", sort = False)["ArmorName"].agg(list)
    ComboList = pd.DataFrame(it.product(*np.array(ArmorGroup)))
    ComboList.columns = ['Helmet', 'Vest', 'Gloves', 'Pants', 'Boots']
    Records = ComboList
    if includeAugCombos:
        AllResults = ComboList.copy()
    ComboList = pd.DataFrame(ComboList.stack(level=0))
    ComboList.columns = ["ArmorName"]
    Records[["Best", "Res1", "Res2", "Res3"]] = [0.0, 0.0, 0.0, 0.0]
    AugDiff = DataCombRes.xs(1, level=1, axis=1) - DataCombRes.xs(0, level=1, axis=1)
    AugDiff = AugDiff.reset_index()
    ResBase = DataCombRes.xs(0, level = 1, axis = 1).reset_index()
    ComboListDiff = ComboList.reset_index().merge(AugDiff[["ArmorName", 0, 1, 2]], how = "left")
    ComboListBase = ComboList.reset_index().merge(ResBase[["ArmorName", 0, 1, 2]], how = "left")
    ComboListDiff = ComboListDiff.drop(["ArmorName"], axis=1)
    ComboListDiff = ComboListDiff.set_index(keys = ["level_0", "level_1"])
    ComboListBase = ComboListBase.drop(["ArmorName"], axis=1)
    ComboListBase = ComboListBase.set_index(keys = ["level_0", "level_1"])
    
    AugComboList = np.array(list(it.product(*[set(it.permutations([1]*i + [0]*(3-i))) for i in ArmorAugSlots])))
    AugComboListNames = ['AugSet', 'Piece', 'On']
    AugComboListIndex = pd.MultiIndex.from_product([range(s)for s in AugComboList.shape], names=AugComboListNames)
    AugComboList = pd.DataFrame({'AugsCombos': AugComboList.flatten()}, index=AugComboListIndex)
    AugComboList = AugComboList.unstack(level=[0, 2])["AugsCombos"]
    AugComboList.index = ["Helmet", "Vest", "Gloves", "Pants", "Boots"]
    
    BestAugsCols = pd.DataFrame(AugComboList[0].stack()).T
    BestAugs = pd.DataFrame(index=Records.index, columns = BestAugsCols.columns)
    RecordsUpdateCols = Records.columns.get_indexer(["Best", "Res1", "Res2", "Res3"])
    
    AllResultsDict = {}
    userUpdateTime = perf_counter()
    for i in AugComboList.columns.levels[0]: #I get memory problems if i load every aug combination at once
        iMultiplier = AugComboList[i].reindex(ComboListDiff.index, axis = "index", level = 1)
        iResult = ComboListDiff * iMultiplier +  ComboListBase
        iResult = iResult.groupby("level_0")[[0, 1, 2]].sum()
        iResult["Best"] = iResult.min(axis=1)
        if includeAugCombos:
            AllResultsDict[i] = iResult["Best"]
        BetterIDs = np.where(iResult["Best"] > Records["Best"])
        Records.iloc[BetterIDs[0], RecordsUpdateCols] = iResult.iloc[BetterIDs][["Best", 0, 1, 2]]
        BestAugs.iloc[BetterIDs] = np.array(AugComboList[i].stack())
        if perf_counter() > userUpdateTime + 5:
            print (f"{i+1}/{len(AugComboList.columns.levels[0])}...")
            userUpdateTime = perf_counter()
        
    AllResults = pd.concat([AllResults, pd.DataFrame(AllResultsDict)], axis = 1)
    RecordsAndAugs = pd.concat([Records, BestAugs], axis=1)
    RecordsAndAugs.to_csv("BestAugs.csv", index = False)
    if includeRes:
        DataCombRes.to_csv("AuggedUnauggedRes.csv")
    if includeAugCombos:
        AllResults.to_csv("AllAugCombos.csv", index = False)


def useraddbonus():
    print ("Creating bonus combo.")
    while True:
        BAE = takeInput("How many points in BAE? (Whole number, 0-25)\n", [isInt, isFloat])
        if BAE == "e":
            break
        Masteries = takeInput("What mastery level? (Whole number, 0-5)\n", [isInt], [0, 5])
        if Masteries == "e":
            break
        BaseCores = takeInput("How many base cores? (whole number, 0-10)\n", [isInt, isFloat])
        if BaseCores == "e":
            break
        Std = takeInput("Standard collections? (1 = yes, 0 = no)\n", [isInt], [0,1])
        if Std == "e":
            break
        Red = takeInput("Red collections? (1 = yes, 0 = no)\n", [isInt], [0,1])
        if Red == "e":
            break
        Bck = takeInput("Black collections? (1 = yes, 0 = no)\n", [isInt], [0,1])
        if Bck == "e":
            break
        Name = ""
        while len(Name) == 0 or Name in bonusList:
            Name = input("Name this combo:\n")
            if Name in bonusList:
                print ("Name already used. Try again.")
            elif Name == "e":
                break
        if Name == "e":
            break
        
        bonusList[Name] = {"BAE":BAE, "Masteries":Masteries, "BaseCores":BaseCores, "Std":Std, "Red": Red, "Bck": Bck}
        pd.DataFrame(bonusList).to_csv("BonusCombos.csv")
        print ("Bonus combo has been saved.")
        
def converttokey(x, xdict):  
    if x in xdict:
        return (x)
    elif x in [str(i) for i in range(1, len(xdict) + 1)]:
        return (list(xdict)[int(x) - 1])
    else:
        return False

def printDictList(dt, complete = False):
    if complete:
        print ("")
        print (pd.DataFrame(dt).T)
        print ("")
    else:
        print ("")
        for i, j in enumerate(dt, start = 1):
            print (f"{i}  {j}")
        print ("")

def userdeletebonus():
    printDictList(bonusList)
    while True:
        to_del = input("Type the number or name of a bonus combo to delete it.\n")
        if to_del == "e":
            return
        to_del = converttokey(to_del, bonusList)
        if to_del:
            del bonusList[to_del]
            pd.DataFrame(bonusList).to_csv("BonusCombos.csv")
            print ("Bonus combo deletion has been saved.")
            printDictList(bonusList)
        else:
            print ("Invalid input.")
            
        
        
        
def userbonus():
    while True:
        task = input("What would you like to do? ('e' to exit at any time)\n"
                     "1  Add bonus combo\n"
                     "2  Delete bonus combo\n"
                     "3  View bonus combos\n")
        match task:
            case "1":
                useraddbonus()
            case "2":
                userdeletebonus()
            case "3":
                printDictList(bonusList, complete = True)
            case "e":
                break
            case _:
                print ("Invalid input.")

def armorListToDataFrame(armorls):
    df = pd.DataFrame(armorls)
    df.columns = ["ArmorName"]
    df = df.merge(Armors[["ArmorName", "ArmorType"]], how = "left")
    df = pd.DataFrame(df.groupby("ArmorType", sort=False)["ArmorName"].apply(pd.Series))
    df = df.unstack().T.apply(lambda x: pd.Series(x.dropna().values))
    df.columns.name = None
    df = df.fillna("")
    df.index = ["" for i in df.index]
    return (df)

def dataFrameToList(armordf):
    ls = armordf.T.values
    ls = ls[ls != ""].flatten()
    ls = list(ls)
    return (ls)

def printFormattedArmorList(armorls):
    df = armorListToDataFrame(armorls)
    print ("")
    print (df)
    print ("")

def useraddarmorquestion(step, sayall = False):
    qL = {"cat":["Helmet", "Vest", "Gloves", "Pants", "Boots"],
                "word":["helmets", "vests", "gloves", "pants", "boots"]}
    allphrase = ", type 'all' to add all armor" if sayall else ""
    armorDisplay = pd.DataFrame(Armors[Armors["ArmorType"] == qL["cat"][step]]["ArmorName"])
    armorDisplay = armorDisplay.reset_index(drop = True)
    armorDisplay.index += 1
    armorDisplay.columns = [""]
    print(armorDisplay)
    while True:
        armorInput = input(f"Type numbers of {qL['word'][step]} you want to use, separated by spaces. Type 'a' to add all {qL['word'][step]}{allphrase}.\n")
        
        if sayall == True and armorInput == "all":
            return list(Armors["ArmorName"]), True
        elif armorInput == "e":
            if sayall:
                return "e", False
            else:
                return "e"
        elif armorInput == "a":
            armorOutput = list(Armors[Armors["ArmorType"] == qL["cat"][step]]["ArmorName"])
            break
        else:
            try:
                armorInput = np.array(list(filter(lambda x: x != "", armorInput.split(" ")))).astype(int)
                armorOutput = list(armorDisplay.loc[armorInput][""])
                break
            except ValueError:
                print ("Invalid input. Use whole numbers.")
            except KeyError:
                print ("Invalid input. Only use available numbers.")
    if sayall:
        return armorOutput, False
    else:
        return armorOutput
    
                
def useraddarmorloop():
    armorcombo = []
    while True:
        newarmor, skip = useraddarmorquestion(step = 0, sayall = True)
        if newarmor == "e":
            return "e"
        armorcombo.extend(newarmor)
        if skip:
            break
        printFormattedArmorList(armorcombo)
        for i in range(1,5):
            newarmor = useraddarmorquestion(i)
            if newarmor == "e":
                return "e"
            armorcombo.extend(newarmor)
            printFormattedArmorList(armorcombo)
        break
    Name = ""
    while len(Name) == 0 or Name in armorList:
        Name = input("Name this armor combo, or enter 'e' to discard.\n")
        if Name == "e":
            return "e"
        elif Name in armorList:
            print ("Name already used. Try again.")
    armorList[Name] = pd.Series(armorcombo)
    pd.DataFrame(armorList).to_csv("ArmorCombos.csv")
    print ("Armor combo has been saved.")
    return 0
    

def useraddarmor():
    print ("Creating armor combo.")
    new_armor = ""
    while not new_armor == "e":
        new_armor = useraddarmorloop()

        

def userdeletearmor():
    printDictList(armorList)
    while True:
        to_del = input("Type the number or name of an armor combo to delete it.\n")
        if to_del == "e":
            return
        to_del = converttokey(to_del, armorList)
        if to_del:
            del armorList[to_del]
            pd.DataFrame(armorList).to_csv("ArmorCombos.csv")
            print ("Armor combo deletion has been saved.")
            printDictList(armorList)
        else:
            print ("Invalid input.")
            
def userviewarmor():
    printDictList(armorList)
    while True:
        toView = input("Type the number or name of an armor combo to view it.\n")
        if toView == "e":
            return
        toView = converttokey(toView, armorList)
        if toView:
            printFormattedArmorList(armorList[toView])
        else:
            print ("Invalid input.")
        
                
def userarmors():
    while True:
        task = input("What would you like to do? ('e' to exit at any time)\n"
                     "1  Add armor combo\n"
                     "2  Delete armor combo\n"
                     "3  View armor combos\n")
        match task:
            case "1":
                useraddarmor()
            case "2":
                userdeletearmor()
            case "3":
                userviewarmor()
            case "e":
                break
            case _:
                print ("Invalid input.")


def userCalcResistances():
    print ("Augged (grade 12) and unaugged resistances will be calculated and sent to 'AuggedUnauggedRes.csv'. Type 'e' to exit at any time.")
    while True:
        
        printDictList(bonusList)
        while True:
            chosenBonus = input("Type the number or name of a bonus combo to select it.\n")
            if chosenBonus == "e":
                return
            chosenBonus = converttokey(chosenBonus, bonusList)
            if chosenBonus:
                chosenBonus = bonusList[chosenBonus]
                break
            else:
                print ("Invalid input.")

        printDictList(armorList)
        while True:
            chosenArmor = input("Type the number or name of an armor combo to select it.\n")
            if chosenArmor == "e":
                return
            chosenArmor = converttokey(chosenArmor, armorList)
            if chosenArmor:
                chosenArmor = armorList[chosenArmor]
                break
            else:
                print ("Invalid input.")
                
        resSettings = ArmorInput(BAE = chosenBonus["BAE"],
                                 Armor = chosenArmor,
                                 Masteries = chosenBonus["Masteries"],
                                 BaseCores = chosenBonus["BaseCores"],
                                 Collections = {"Std":chosenBonus["Std"], "Red":chosenBonus["Red"], "Bck":chosenBonus["Bck"]},
                                 Augs = [12, 12, 12]
                                )
        
        DataCombRes = calcResistances(resSettings)
        DataCombRes.to_csv("AuggedUnauggedRes.csv")
        print ("Resistances have been calculated.")
        
def usergetoptimalaugs():
    print ("The optimal augs for selected armor combos will be calculated and sent to 'BestAugs.csv'. Type 'e' to exit at any time.")
    while True:

        printDictList(bonusList)
        while True:
            chosenBonus = input("Type the number or name of a bonus combo to select it.\n")
            if chosenBonus == "e":
                return
            chosenBonus = converttokey(chosenBonus, bonusList)
            if chosenBonus:
                chosenBonus = bonusList[chosenBonus]
                break
            else:
                print ("Invalid input.")

        printDictList(armorList)
        while True:
            chosenArmor = input("Type the number or name of an armor combo to select it.\n")
            if chosenArmor == "e":
                return
            chosenArmor = converttokey(chosenArmor, armorList)
            if chosenArmor:
                chosenArmor = armorList[chosenArmor]
                break
            else:
                print ("Invalid input.")
                
        resSettings = ArmorInput(BAE = chosenBonus["BAE"],
                                 Armor = chosenArmor,
                                 Masteries = chosenBonus["Masteries"],
                                 BaseCores = chosenBonus["BaseCores"],
                                 Collections = {"Std":chosenBonus["Std"], "Red":chosenBonus["Red"], "Bck":chosenBonus["Bck"]},
                                 Augs = [12, 12, 12]
                                )
        while True:
            freeAugs = input("How many available augs for each piece? Type 5 numbers separated by spaces, each between 0-3.\n")
            if freeAugs == "e":
                return
            try:
                freeAugs = np.array(list(filter(lambda x: x != "", freeAugs.split(" ")))).astype(int)
                if len(freeAugs) != 5:
                    print ("Invalid input. Must be 5 numbers.")
                elif (freeAugs < 0).any() or (freeAugs > 3).any():
                    print ("Invalid input. Numbers must be between 0-3")
                else:
                    break
            except ValueError:
                print ("Invalid input.")

            
        
        includeRes = takeInput("Include 'AuggedUnauggedRes.csv'? (1 = yes, 0 = no)\n", [isInt], [0,1])
        if includeRes == "e":
            break

        includeAugCombos = takeInput("Include 'AllAugCombos.csv'? (warning: may be large file) (1 = yes, 0 = no)\n", [isInt], [0,1])
        if includeAugCombos == "e":
            break
            
        permuteOptimise(resSettings, freeAugs, includeRes = includeRes, includeAugCombos = includeAugCombos)
        print ("Optimised resistances have been calculated.")
            
        
        
        
        

def user():
    while True:
        task = input("Select a task:\n"
                     "1  Modify bonus combos\n"
                     "2  Modify armor combos\n"
                     "3  Calc resistances\n"
                     "4  Get optimal augs\n"
                     "5  Quit\n"
                    )
        match task:
            case "1":
                userbonus()
            case "2":
                userarmors()
            case "3":
                userCalcResistances()
            case "4":
                usergetoptimalaugs()
            case "5":
                break
            case _:
                print ("Invalid input.")
        
    
user()

