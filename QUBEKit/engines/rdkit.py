#!/usr/bin/env python3

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit.Chem.rdForceFieldHelpers import MMFFOptimizeMolecule, UFFOptimizeMolecule
from rdkit.Geometry.rdGeometry import Point3D


class RDKit:
    """Class for controlling useful RDKit functions."""

    @staticmethod
    def mol_input_to_rdkit_mol(mol_input, name=None):
        """
        :param mol_input: pathlib.Path of the filename provided or the smiles string
        :param name:
        :return: RDKit molecule object generated from its file (or None if incorrect file type is provided).
        """

        # Interpret the smiles string
        if isinstance(mol_input, str):
            return RDKit.smiles_to_rdkit_mol(mol_input, name)

        # Read the file
        if mol_input.suffix == ".pdb":
            return Chem.MolFromPDBFile(mol_input.name, removeHs=False)
        elif mol_input.suffix == ".mol2":
            return Chem.MolFromMol2File(mol_input.name, removeHs=False)
        elif mol_input.suffix == ".mol":
            return Chem.MolFromMolFile(mol_input.name, removeHs=False)

        return None

    @staticmethod
    def smiles_to_rdkit_mol(smiles_string, name=None):
        """
        Converts smiles strings to RDKit mol object.
        :param smiles_string: The hydrogen free smiles string
        :param name: The name of the molecule this will be used when writing the pdb file
        :return: The RDKit molecule
        """

        mol = AllChem.MolFromSmiles(smiles_string)
        if name is None:
            name = input("Please enter a name for the molecule:\n>")
        mol.SetProp("_Name", name)
        mol_hydrogens = AllChem.AddHs(mol)
        AllChem.EmbedMolecule(mol_hydrogens, AllChem.ETKDG())
        AllChem.SanitizeMol(mol_hydrogens)

        return mol_hydrogens

    @staticmethod
    def mm_optimise(filename, ff="MMF"):
        """
        Perform rough preliminary optimisation to speed up later optimisations.
        :param filename: The Path of the input file
        :param ff: The Force field to be used either MMF or UFF
        :return: The name of the optimised pdb file that is made
        """

        # Get the rdkit molecule
        mol = RDKit.mol_input_to_rdkit_mol(filename)

        {"MMF": MMFFOptimizeMolecule, "UFF": UFFOptimizeMolecule}[ff](mol)

        AllChem.MolToPDBFile(mol, f"{filename.stem}_rdkit_optimised.pdb")

        return f"{filename.stem}_rdkit_optimised.pdb"

    @staticmethod
    def rdkit_descriptors(rdkit_mol):
        """
        Use RDKit Descriptors to extract properties and store in Descriptors dictionary.
        :param rdkit_mol: The molecule input file
        :return: descriptors dictionary
        """

        # Use RDKit Descriptors to extract properties and store in Descriptors dictionary
        return {
            "Heavy atoms": Descriptors.HeavyAtomCount(rdkit_mol),
            "H-bond donors": Descriptors.NumHDonors(rdkit_mol),
            "H-bond acceptors": Descriptors.NumHAcceptors(rdkit_mol),
            "Molecular weight": Descriptors.MolWt(rdkit_mol),
            "LogP": Descriptors.MolLogP(rdkit_mol),
        }

    @staticmethod
    def get_smiles(filename):
        """
        Use RDKit to load in the pdb file of the molecule and get the smiles code.
        :param filename: The molecule input file
        :return: The smiles string
        """

        rdkit_mol = RDKit.mol_input_to_rdkit_mol(filename)

        return Chem.MolToSmiles(rdkit_mol, isomericSmiles=True, allHsExplicit=True)

    @staticmethod
    def get_smarts(filename):
        """
        Use RDKit to get the smarts string of the molecule.
        :param filename: The molecule input file
        :return: The smarts string
        """

        mol = RDKit.mol_input_to_rdkit_mol(filename)

        return Chem.MolToSmarts(mol)

    @staticmethod
    def get_mol(filename):
        """
        Use RDKit to generate a mol file.
        :param filename: The molecule input file
        :return: The name of the mol file made
        """

        mol = RDKit.mol_input_to_rdkit_mol(filename)

        mol_name = f"{filename.stem}.mol"
        Chem.MolToMolFile(mol, mol_name)

        return mol_name

    @staticmethod
    def generate_conformers(rdkit_mol, conformer_no=10):
        """
        Generate a set of x conformers of the molecule
        :param conformer_no: The amount of conformers made for the molecule
        :param rdkit_mol: The name of the input file
        :return: A list of conformer position arrays
        """

        AllChem.EmbedMultipleConfs(rdkit_mol, numConfs=conformer_no)
        positions = rdkit_mol.GetConformers()

        return [conformer.GetPositions() for conformer in positions]

    @staticmethod
    def find_symmetry_classes(rdkit_mol):
        """
        Generate list of tuples of symmetry-equivalent (homotopic) atoms in the molecular graph
        based on: https://sourceforge.net/p/rdkit/mailman/message/27897393/
        Our thanks to Dr Michal Krompiec for the symmetrisation method and its implementation.
        :param rdkit_mol: molecule to find symmetry classes for (rdkit mol class object)
        :return: A dict where the keys are the atom indices and the values are their type
        (type is arbitrarily based on index; only consistency is needed, no specific values)
        """

        # Check CIPRank is present for first atom (can assume it is present for all afterwards)
        if not rdkit_mol.GetAtomWithIdx(0).HasProp("_CIPRank"):
            Chem.AssignStereochemistry(
                rdkit_mol, cleanIt=True, force=True, flagPossibleStereoCenters=True
            )

        # Array of ranks showing matching atoms
        cip_ranks = np.array(
            [int(atom.GetProp("_CIPRank")) for atom in rdkit_mol.GetAtoms()]
        )

        # Map the ranks to the atoms to produce a list of symmetrical atoms
        atom_symmetry_classes = [
            np.where(cip_ranks == rank)[0].tolist()
            for rank in range(max(cip_ranks) + 1)
        ]

        # Convert from list of classes to dict where each key is an atom and each value is its class (just a str)
        atom_symmetry_classes_dict = {}
        # i will be used to define the class (just index based)
        for i, sym_class in enumerate(atom_symmetry_classes):
            for atom in sym_class:
                atom_symmetry_classes_dict[atom] = str(i)

        return atom_symmetry_classes_dict

    @staticmethod
    def get_conformer_rmsd(rdkit_mol, ref_index, align_index):
        """
        Get the rmsd between the current rdkit molecule and the coordinates provided
        :param rdkit_mol: rdkit representation of the molecule, conformer 0 is the base
        :param ref_index: the conformer index of the refernce
        :param align_index: the conformer index which should be aligned
        :return: the rmsd value
        """

        return Chem.AllChem.GetConformerRMS(rdkit_mol, ref_index, align_index)

    @staticmethod
    def add_conformer(rdkit_mol, conformer_coordinates):
        """
        Add a new conformation to the rdkit molecule
        :param conformer_coordinates:  A numpy array of the coordinates to be added
        :param rdkit_mol: The rdkit molecule instance
        :return: The rdkit molecule with the conformer added
        """

        conformer = Chem.Conformer()
        for i, coord in enumerate(conformer_coordinates):
            atom_position = Point3D(*coord)
            conformer.SetAtomPosition(i, atom_position)

        rdkit_mol.AddConformer(conformer, assignId=True)

        return rdkit_mol
