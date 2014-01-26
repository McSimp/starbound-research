starbound-research
==================
This repository contains various scripts and data structures to (hopefully) help with modding Starbound.

Data Structures
---------------
You can find `*.bt` files in the directories named after the versions of Starbound. Only versions which have format altering changes will have a directory associated with them.

`*.bt` files are created to be read by [010 Editor](http://www.sweetscape.com/010editor/), but have C-like syntax so it should be pretty easy to follow along.

The latest game version which had a format altering change was **Furious Koala**.

ListItems.py
------------
**NOTE:** As of Furious Koala, you will need to extract the assets using the `asset_unpacker` utility in your game folder before using this.

Run this script from the assets folder in your Starbound installation and it'll generate a JSON file containing all items in the game, and where to find their icons and info files.

You can see an example of the output at https://gist.github.com/McSimp/7955426

Contact
-------
If you've got more questions, or you've got something to contribute, you can add me on Steam: http://steamcommunity.com/id/McSimp
