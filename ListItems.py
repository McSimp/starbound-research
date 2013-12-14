import os
import json
import re

###############################################
# Run this from the root of the assets folder #
###############################################

# Some code from http://www.lifl.fr/~riquetd/parse-a-json-file-with-comments.html
# "Parse a JSON file with comments"

comment_re = re.compile(
    '(^)?[^\S\n]*/(?:\*(.*?)\*/[^\S\n]*|/[^\n]*)($)?',
    re.DOTALL | re.MULTILINE
)

def parse_json(content):
    """ Parse a JSON file
        First remove comments and then use the json module package
    """
    ## Looking for comments
    match = comment_re.search(content)
    while match:
        # single line comment
        content = content[:match.start()] + content[match.end():]
        match = comment_re.search(content)

    # Replace -. with -0.
    content = content.replace("-.", "-0.")

    # Return json file
    return json.loads(content)

def getPath(root, file):
    path = os.path.join(root, file)
    return path[2:].replace("\\", "/")

imageKeys = ["inventoryIcon", "image"]
def getImageFromData(data):
    # Not all items just have an "inventoryIcon"
    for key in imageKeys:
        if key in data:
            return data[key]
    return None

def getItemDetails(root, filename):
    itemPath = getPath(root, filename)
    #print(itemPath)

    fh = open(itemPath, "r")
    data = parse_json(fh.read())

    # It will either have objectName or itemName
    try:
        itemName = data["itemName"]
    except KeyError:
        itemName = data["objectName"]

    # Not all items have a static inventory icon
    image = getImageFromData(data)
    if image is not None:
        iconPath = getPath(root, image)
    else:
        print("No image for: " + itemPath)
        iconPath = None

    return itemName, { "itemPath": itemPath, "iconPath": iconPath }

def getAllItems(itemType):
    itemDict = {}
    extension = "." + itemType
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(extension):
                itemName, details = getItemDetails(root, file)
                itemDict[itemName] = details

    return itemDict

allItems = {}

# "generatedsword", "generatedgun", "generatedshield", "codexitem"
itemTypes = [
    "item", 
    "matitem", "miningtool", "flashlight", "wiretool", "beamaxe", 
    "tillingtool", "painttool", "gun", "sword", "harvestingtool", 
    "head", "chest", "legs", "back", "coinitem", "consumable", 
    "blueprint", "techitem", "instrument", "grapplinghook", 
    "thrownitem", "celestial", "object"
]

for itemType in itemTypes:
    allItems[itemType] = getAllItems(itemType)

outFile = open("items.json", "w")
json.dump(allItems, outFile)

print("All items written to items.json")
