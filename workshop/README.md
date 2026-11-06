# Workshop guide: exploring proteins with Claude and PyMOL

These exercises teach structural biology by asking questions in plain language. Students don't need to know any PyMOL commands. Claude runs PyMOL, and students focus on what the structure shows.

## Before the session

1. Install PyMOL and Claude Code.
2. Run `pip install git+https://github.com/OmarArias-Gaguancela/pymol-quickvisuals`, then `pymol-quickvisuals setup`.
3. Run `pymol-quickvisuals doctor`. Every line should say `ok`.
4. Open Claude Code and ask: *"Check that PyMOL is connected."* PyMOL opens by itself.

## Exercise 1: Hemoglobin and oxygen (20 min)

Structure: **1HHO** (oxygenated human hemoglobin)

1. *"Load 1HHO and tell me what's in it: chains, ligands, and anything else."*
   - Discuss: why are there two kinds of chains? What are the HEM and OXY groups?
2. *"Remove the waters and anything from the crystallization buffer."*
   - Discuss: what is a crystallographic water? Why is phosphate there?
3. *"Show the protein as a cyan cartoon and the hemes with oxygen as yellow spheres."*
4. *"Zoom into one heme. Show the histidine bonded to the iron as sticks and measure the distance."*
   - Discuss: what is the proximal histidine, and why does the Fe–N distance matter?
5. *"Compare with deoxy hemoglobin 4HHB: align them and color the parts that moved."*
   - Discuss: the T-to-R transition and cooperativity.

## Exercise 2: An enzyme active site (20 min)

Structure: **1HSG** (HIV-1 protease with inhibitor)

1. *"Load 1HSG and describe it."*
2. *"Show residues within 4 Å of the inhibitor as sticks and label them."*
3. *"Which of those residues come from each chain? Why does that matter for a dimeric enzyme?"*
4. *"Show hydrogen bonds between the inhibitor and the protein."*

## Exercise 3: Make a figure (15 min)

Using either structure:

1. *"Make a publication-quality figure: white background, ray-traced, 1600×1200."*
2. *"Save it as figure1.png in my current folder."*
3. Students compare figures and discuss what makes a structure figure clear.

## Tips for instructors

- Encourage students to ask **why** questions ("why is this residue here?"). Claude explains as it works.
- If something looks wrong, students can say *"that's not right, the ligand is hidden"*. Claude takes a screenshot and fixes it.
- Each student needs their own PyMOL and Claude Code. The server controls the PyMOL on the same computer.
