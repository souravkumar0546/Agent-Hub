"""
Material Taxonomy Definitions
=============================
All L2 category taxonomies loaded from 'Taxonomy L2 final-29.10.2025.xlsx'.
Definitions and examples are EXACT copies from the Excel — do not paraphrase.

Category names include the material group code in brackets, e.g.:
    "Analytical Consumables (YS17)"
"""

MATERIAL_TAXONOMIES: dict[str, dict] = {
    # ──────────────────────────────────────────────────────────────────────
    #  ZSC1 — Consumables (Type 1)
    # ──────────────────────────────────────────────────────────────────────
    "ZSC1": {
        "label": "Consumables - ZSC1",
        "override_rules": (
            "- Having a catalogue number does NOT mean Non-CAS. Most chemicals have both CAS and catalogue numbers.\n"
            "- Common chemicals (acids, bases, solvents, salts like Acetone, NaOH, HCl, Methanol, NaCl) are ALWAYS Lab Reagents & QC Supplies — NEVER Non-CAS.\n"
            "- A drug name (e.g. Telmisartan, Epinephrine, Cisplatin) bought in mg quantities from REFERENCE STANDARD vendors (Cayman, Clearsynth, TRC, MedChemExpress, Tocris, LGC, Cerilliant, USP) → RLD & Reference Standards, NOT Medicinal Supplies.\n"
            "- But a drug/antibiotic name (e.g. Gentamicin, Penicillin, Amphotericin B) from CELL CULTURE vendors (Gibco, Lonza, Cytiva, Thermo) at working concentrations (mg/mL) is a cell culture supplement → Lab Reagents & QC Supplies, NOT RLD.\n"
            "- Catalysts (Palladium on Carbon, Platinum oxide, Raney Nickel) are NOT reference standards → Lab Reagents & QC Supplies or Process Consumables.\n"
            "- Deuterated compounds (D3, D4, D6, D8 in the name) are ALWAYS reference standards → RLD & Reference Standards.\n"
            "- Drug metabolites (Hydroxy-X, Desmethyl-X, Nor-X) are ALWAYS reference standards → RLD & Reference Standards.\n"
            "- Medicinal Supplies is ONLY for patient-ready finished dosage forms (tablet strips, injection vials, syrups) bought from a PHARMACY for an employee clinic — NOT for lab-grade compounds from research suppliers.\n"
            "- Process & Testing Solvents are organic or inorganic liquids (Methanol, Acetone, IPA, DCM, Hexane, Acetonitrile) used in manufacturing or QC testing — classify here ONLY when description clearly indicates solvent use in process/testing."
        ),
        "categories": {
            "Analytical Consumables (YS17)": {
                "definition": "Items used in analytical testing, measurement, or laboratory instrumentation.",
                "examples": "Chromatography columns, filter papers, cuvettes & Etc",
            },
            "Process Consumables (YS18)": {
                "definition": "Materials consumed during manufacturing or process operations, not part of the final product.",
                "examples": "Filters, process gaskets,Cell line, blood matrix Etc, Gases",
            },
            "Safety Consumables (YS19)": {
                "definition": "Disposable or regularly replaced items used for personal or workplace safety.",
                "examples": "PPE, gloves, masks, safety goggles & Etc, ETP chemicals, scrubber",
            },
            "Engineering & Maintenance Consumables (YS20)": {
                "definition": "Items consumed during equipment upkeep, repairs, or technical services.",
                "examples": "Lubricants, sealants, gaskets, tapes, electrical connectors used for upkeep of lab/process equipment & Etc, Boiler /utility consumable",
            },
            "Laboratory Supplies (YS21)": {
                "definition": "Everyday laboratory supplies used across multiple activities.",
                "examples": "Glassware, plasticware, pipette tips, weighing boats, lab cleaning materials, sample storage items & Etc, Diagnostics",
            },
            "Media & Buffers (YS22)": {
                "definition": "Ready-to-use or prepared formulations that provide a controlled chemical or biological environment for growth, reaction, or stabilization in laboratory or production processes.",
                "examples": "Cell culture media, bacterial growth media, phosphate-buffered saline (PBS), Tris buffer.",
            },
            "Non-CAS based Chemicals (YS23)": {
                "definition": "Chemicals without CAS Nos. but getting utilized using Catalogue Nos.",
                "examples": "",
            },
            "RLD & Reference Standards (YS24)": {
                "definition": (
                    "In the context of pharmaceuticals, reference standards are highly characterized materials used as benchmarks to ensure "
                    "the identity, purity, potency, and quality of active pharmaceutical ingredients (APIs) and final products. They are essential "
                    "for analytical testing and regulatory compliance.\n"
                    "A Reference Manufactured Product is a product that has been manufactured under defined and approved conditions and is used "
                    "as a benchmark or comparator for evaluation, control, verification, or regulatory purposes."
                ),
                "examples": "",
            },
            "Medicinal Supplies (YS26)": {
                "definition": (
                    "Medicine Supplies refer to over\u2011the\u2011counter (OTC) medicines that do not require a medical prescription "
                    "and are procured by the organization exclusively for employee health and welfare. These medicines are used and dispensed "
                    "through the Occupational Health Centre (OHC) for first aid, minor ailments, preventive care, and immediate medical support to employees."
                ),
                "examples": "Injections, Tablets, medicines etc, Animal feed, Animal diet",
            },
            "Lab Reagents & QC Supplies (YS27)": {
                "definition": (
                    "QC Supplies and Laboratory Reagents include chemicals, reagents, reference materials, standards, solvents, and consumables "
                    "used in Quality Control (QC) and laboratory testing activities to analyze, test, verify, and release raw materials, intermediates, "
                    "finished products, and in\u2011process samples in compliance with GMP and regulatory requirements."
                ),
                "examples": (
                    "Callibrator, control, reagents, antibodies etc, Analytical reagents and chemicals\n"
                    "Buffers, acids, bases, and solvents\n"
                    "Reference standards and control samples\n"
                    "Culture media and test kits\n"
                    "Volumetric solutions and laboratory consumables used for testing"
                ),
            },
            "Molecular Biology Consumables (YS30)": {
                "definition": (
                    "Molecular Biology Consumables are single\u2011use or limited\u2011use laboratory materials, reagents, and kits used in molecular "
                    "biology workflows to support DNA, RNA, protein, and cell\u2011based experiments, including sample preparation, amplification, "
                    "cloning, expression, detection, and analysis."
                ),
                "examples": "Gene, Protein, DNA, RNA, Neuclotides, microbes,marker",
            },
            "Process & Testing Solvents (YS64)": {
                "definition": (
                    "Process and Testing Solvents are organic or inorganic liquids used during manufacturing (process) and quality control (testing) "
                    "activities to support chemical reactions, extraction, purification, cleaning, sample preparation, and analytical testing of raw "
                    "materials, intermediates, APIs, and finished products."
                ),
                "examples": "",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZSC2 — Consumables (Type 2)
    # ──────────────────────────────────────────────────────────────────────
    "ZSC2": {
        "label": "Consumables - ZSC2",
        "override_rules": (
            "- Having a catalogue number does NOT mean Non-CAS. Most chemicals have both CAS and catalogue numbers.\n"
            "- Common chemicals (acids, bases, solvents, salts like Acetone, NaOH, HCl, Methanol, NaCl) are ALWAYS Lab Reagents & QC Supplies — NEVER Non-CAS.\n"
            "- A drug name bought in mg quantities from REFERENCE STANDARD vendors → RLD & Reference Standards, NOT Medicinal Supplies.\n"
            "- Catalysts are NOT reference standards → Lab Reagents & QC Supplies or Process Consumables.\n"
            "- Deuterated compounds (D3, D4, D6, D8 in the name) are ALWAYS reference standards → RLD & Reference Standards.\n"
            "- Drug metabolites (Hydroxy-X, Desmethyl-X, Nor-X) are ALWAYS reference standards → RLD & Reference Standards.\n"
            "- Medicinal Supplies is ONLY for patient-ready finished dosage forms bought from a PHARMACY for an employee clinic.\n"
            "- Process & Testing Solvents: organic or inorganic liquids used in manufacturing or QC testing."
        ),
        "categories": {
            "Analytical Consumables (YS17)": {
                "definition": "Items used in analytical testing, measurement, or laboratory instrumentation.",
                "examples": "Chromatography columns, filter papers, cuvettes & Etc",
            },
            "Process Consumables (YS18)": {
                "definition": "Materials consumed during manufacturing or process operations, not part of the final product.",
                "examples": "Filters, process gaskets,Cell line, blood matrix Etc, Gases",
            },
            "Safety Consumables (YS19)": {
                "definition": "Disposable or regularly replaced items used for personal or workplace safety.",
                "examples": "PPE, gloves, masks, safety goggles & Etc, ETP chemicals, scrubber",
            },
            "Engineering & Maintenance Consumables (YS20)": {
                "definition": "Items consumed during equipment upkeep, repairs, or technical services.",
                "examples": "Lubricants, sealants, gaskets, tapes, electrical connectors used for upkeep of lab/process equipment & Etc, Boiler /utility consumable",
            },
            "Laboratory Supplies (YS21)": {
                "definition": "Everyday laboratory supplies used across multiple activities.",
                "examples": "Glassware, plasticware, pipette tips, weighing boats, lab cleaning materials, sample storage items & Etc, Animal feed",
            },
            "Media & Buffers (YS22)": {
                "definition": "Ready-to-use or prepared formulations that provide a controlled chemical or biological environment for growth, reaction, or stabilization in laboratory or production processes.",
                "examples": "Cell culture media, bacterial growth media, phosphate-buffered saline (PBS), Tris buffer.",
            },
            "Non-CAS based Chemicals (YS23)": {
                "definition": "Chemicals without CAS Nos. but getting utilized using Catalogue Nos.",
                "examples": "",
            },
            "RLD & Reference Standards (YS24)": {
                "definition": (
                    "In the context of pharmaceuticals, reference standards are highly characterized materials used as benchmarks to ensure "
                    "the identity, purity, potency, and quality of active pharmaceutical ingredients (APIs) and final products. They are essential "
                    "for analytical testing and regulatory compliance.\n"
                    "A Reference Manufactured Product is a product that has been manufactured under defined and approved conditions and is used "
                    "as a benchmark or comparator for evaluation, control, verification, or regulatory purposes."
                ),
                "examples": "",
            },
            "Medicinal Supplies (YS26)": {
                "definition": (
                    "Medicine Supplies refer to over\u2011the\u2011counter (OTC) medicines that do not require a medical prescription "
                    "and are procured by the organization exclusively for employee health and welfare. These medicines are used and dispensed "
                    "through the Occupational Health Centre (OHC) for first aid, minor ailments, preventive care, and immediate medical support to employees."
                ),
                "examples": "",
            },
            "House Keeping Supplies (YS25)": {
                "definition": (
                    "Housekeeping Supplies are consumable materials, cleaning agents, tools, and hygiene items used to maintain cleanliness, "
                    "sanitation, order, and safety across office, laboratory, manufacturing, and common facility areas. These supplies support "
                    "routine cleaning, waste management, hygiene control, and workplace safety, and do not form part of production, testing, or laboratory processes."
                ),
                "examples": (
                    "dustpan, tea mug, tape, tissue roll etc, Admin supplier, Floor cleaners, disinfectants, detergents\n"
                    "Glass cleaners, surface cleaners, degreasers\n"
                    "Toilet cleaners, descalers, hand wash liquids"
                ),
            },
            "Lab Reagents & QC Supplies (YS27)": {
                "definition": (
                    "QC Supplies and Laboratory Reagents include chemicals, reagents, reference materials, standards, solvents, and consumables "
                    "used in Quality Control (QC) and laboratory testing activities to analyze, test, verify, and release raw materials, intermediates, "
                    "finished products, and in\u2011process samples in compliance with GMP and regulatory requirements."
                ),
                "examples": "Callibrator, control, reagents, antibodies etc",
            },
            "Molecular Biology Consumables (YS30)": {
                "definition": (
                    "Molecular Biology Consumables are single\u2011use or limited\u2011use laboratory materials, reagents, and kits used in molecular "
                    "biology workflows to support DNA, RNA, protein, and cell\u2011based experiments, including sample preparation, amplification, "
                    "cloning, expression, detection, and analysis."
                ),
                "examples": "Gene, Protein, DNA, RNA, Neuclotides, microbes,marker",
            },
            "Process & Testing Solvents (YS64)": {
                "definition": (
                    "Process and Testing Solvents are organic or inorganic liquids used during manufacturing (process) and quality control (testing) "
                    "activities to support chemical reactions, extraction, purification, cleaning, sample preparation, and analytical testing of raw "
                    "materials, intermediates, APIs, and finished products."
                ),
                "examples": "",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZRDM — Raw Materials
    # ──────────────────────────────────────────────────────────────────────
    "ZRDM": {
        "label": "Raw Materials - ZRDM",
        "override_rules": (
            "- KSM & Intermediates are chemical building blocks in API synthesis — NOT finished APIs.\n"
            "- Catalysts speed up reactions without being consumed — classify as Catalysts, not Reagents.\n"
            "- Solvents dissolve/extract/transport — classify based on function, not name.\n"
            "- Excipients are inactive ingredients in dosage forms — NOT APIs.\n"
            "- Research KSM are small-quantity R&D building blocks, distinct from production-scale KSM.\n"
            "- API is the active ingredient itself — only classify here if it IS the final active substance."
        ),
        "categories": {
            "KSM & Intermediates (YS35)": {
                "definition": "Chemical substances that are critical to the synthesis of an active ingredient, forming a significant structural fragment of the final molecule. Intermediates are products of earlier synthesis steps that are further transformed into the final product.",
                "examples": "Protected amino acids, advanced intermediates in API synthesis.",
            },
            "Reagents (YS36)": {
                "definition": "Chemicals used to cause or facilitate a chemical reaction without necessarily being incorporated into the final product structure.",
                "examples": "Oxidizing agents, reducing agents, coupling agents, titration reagents.",
            },
            "Solvents (YS37)": {
                "definition": "Liquid medium used to dissolve, extract, suspend, or transport other substances in a process without chemically altering them under standard conditions.",
                "examples": "Methanol, dichloromethane, toluene, water (when used as process solvent).",
            },
            "Catalysts (YS39)": {
                "definition": "Substance that increases the rate of a chemical reaction without being consumed in the process, enabling greater efficiency and selectivity.",
                "examples": "Palladium on carbon, enzyme catalysts, organometallic complexes.",
            },
            "Excipients (YS40)": {
                "definition": (
                    "An excipient is any intentionally added ingredient in a pharmaceutical dosage form other than the Active Pharmaceutical "
                    "Ingredient (API). Excipients do not provide therapeutic effect but are included to support the manufacture, stability, delivery, "
                    "performance, quality, and patient acceptability of the drug product."
                ),
                "examples": "",
            },
            "Research Key Starting Materials (YS35)": {
                "definition": "Specialized starting materials critical to R&D projects, often in smaller quantities, used in early-stage synthesis of target molecules during research and development.",
                "examples": "Rare or novel synthetic building blocks, lab-scale custom intermediates.",
            },
            "API (YS41)": {
                "definition": (
                    "An Active Pharmaceutical Ingredient (API) is any substance or mixture of substances that is intended to be used in the "
                    "manufacture of a drug product and that, when incorporated into the finished dosage form, provides the pharmacological activity "
                    "or other direct effect in the diagnosis, cure, mitigation, treatment, or prevention of disease, or affects the structure or "
                    "function of the human or animal body."
                ),
                "examples": "",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZCAP — Capital Equipment
    # ──────────────────────────────────────────────────────────────────────
    "ZCAP": {
        "label": "Capex - ZCAP",
        "override_rules": "",
        "categories": {
            "Analytical Equipment (YS01)": {
                "definition": "Precision instruments and devices used for qualitative or quantitative analysis of materials, enabling measurement, detection, and characterization in laboratory or production environments.",
                "examples": "HPLCs, spectrophotometers, particle sizers & Etc",
            },
            "Process Equipment (YS02)": {
                "definition": "Machinery and systems directly involved in manufacturing, synthesis, or processing activities, contributing to the transformation of raw materials into finished or intermediate products.",
                "examples": "Reactors, filtration units, mixers, dryers & Etc",
            },
            "Storage & Cleaning Equipment (YS03)": {
                "definition": "Non-core operational equipment that assists in day-to-day activities, handling, storage, or environmental control but is not directly involved in production or processing steps.",
                "examples": "Laboratory refrigerators, freezers, material handling trolleys, storage cabinets, vaccum cleaners, scrubbers, lawn movers & Etc",
            },
            "IT Hardware & Network Equipment (YS04)": {
                "definition": "Physical computing and peripheral devices used for data processing, storage, and operational control in business, laboratory, and manufacturing settings.",
                "examples": "Servers, desktop computers, printers, barcode scanners & Etc",
            },
            "IT Software (Capex) (YS05)": {
                "definition": "Perpetual licenses",
                "examples": "Perpetual licenses",
            },
            "Civil & Interior (YS06)": {
                "definition": (
                    "Civil items refer to structural and core construction works that form the basic framework and permanent infrastructure "
                    "of a building or facility. These items are essential for strength, stability, and safety of the structure.\n"
                    "Interior items refer to non-structural works and finishes executed inside the building to make spaces functional, "
                    "aesthetic, and usable after civil construction is completed."
                ),
                "examples": (
                    "Interior items refer to non-structural works and finishes executed inside the building to make spaces functional, "
                    "aesthetic, and usable after civil construction is completed.\n"
                    "False ceiling, flooring (tiles/vinyl/carpet), wall paneling, painting, partitions, modular furniture, doors & shutters, "
                    "lighting fixtures, blinds, washroom fittings"
                ),
            },
            "Mechanical, Electrical & Piping (YS07)": {
                "definition": "Building service systems that provide essential utilities and environmental control, typically installed as part of facility infrastructure.",
                "examples": "Mechanical, Electrical and Piping & Etc",
            },
            "Safety Equipment (YS08)": {
                "definition": "Fixed or portable equipment designed to protect personnel, property, and processes from hazards, emergencies, or contamination.",
                "examples": "PPEs, FAS, PA System, CCTV & Fire extinguishers & Etc",
            },
            "Utility Equipment (YS09)": {
                "definition": "Facility-scale systems that generate, distribute, or control essential operational services such as heating, cooling, air, steam, or water.",
                "examples": (
                    "HVAC systems (Air Handling Units, HEPA filters), Material Handling Equipment (Trolleys, Pallet Jacks, Forklifts), "
                    "Purified Water Systems (PW, WFI generation & distribution), Steam Generators / Boilers, Air Compressors & Vacuum Pumps, "
                    "Chillers and Cooling Towers & Etc"
                ),
            },
            "Laboratory Furniture (YS10)": {
                "definition": "Specialized fixtures and fittings used in laboratories to provide safe, functional, and durable infrastructure for scientific and R&D activities.",
                "examples": "Fume Hood, Cabinets, Island bench, Wall bench, Antivibration table",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ERSA — Spares
    # ──────────────────────────────────────────────────────────────────────
    "ERSA": {
        "label": "Spares - ERSA",
        "override_rules": "",
        "categories": {
            "Civil & Interior Spares (YS32)": {
                "definition": "Materials, fixtures, or components for structural works, finishes, and workspace interiors.",
                "examples": "Flooring tiles, modular lab bench parts, false ceiling panels & Etc",
            },
            "Analytical Equipment Spares (YS11)": {
                "definition": "Replacement parts or components for laboratory analytical instruments, ensuring continued accuracy and performance.",
                "examples": "Detector lamps for HPLC, GC columns, spectrophotometer cuvettes, sample trays & Etc",
            },
            "Process Equipment Spares (YS12)": {
                "definition": "Replacement parts for machinery used in manufacturing or processing, ensuring minimal downtime and operational continuity.",
                "examples": "Reactor seals, filter elements, agitator blades, pump impellers & Etc",
            },
            "IT Hardware & Network Equipment Spares (YS13)": {
                "definition": "Replacement components for computing and peripheral devices.",
                "examples": "Hard drives, RAM modules, power supplies for desktops/servers & Etc",
            },
            "Mechanical, Electrical and Piping Spares (YS14)": {
                "definition": "Spare parts or components for building service systems integrated into facility infrastructure.",
                "examples": "Electrical breakers, plumbing valves etc.",
            },
            "Storage & Cleaning Equipment Spares (YS59)": {
                "definition": "Parts for auxiliary equipment used in operations, handling, or storage, but not directly involved in production.",
                "examples": "Refrigerator compressors, Trolleys, trolley wheels, storage cabinet locks & Etc",
            },
            "IT Software (Opex) (YS60)": {
                "definition": "",
                "examples": "",
            },
            "Safety Equipment Spares (YS61)": {
                "definition": "Parts for auxiliary equipment used in operations, handling, or storage, but not directly involved in production.",
                "examples": "Refrigerator compressors, trolley wheels, storage cabinet locks & Etc",
            },
            "Utility Equipment Spares (YS62)": {
                "definition": "Spare parts for facility-scale utility systems that provide operational services.",
                "examples": "Compressor units, Condenser coils & evaporator fans, Air filters, ducts, and dampers, Cooling tower fan blades, gearboxes & Etc",
            },
            "Measuring & General Purpose Instruments (YS63)": {
                "definition": (
                    "Measuring and General\u2011Purpose Instruments are devices used to measure, monitor, indicate, or verify physical, "
                    "chemical, or environmental parameters required for routine laboratory, manufacturing, engineering, quality, and facility operations."
                ),
                "examples": "",
            },
            "IT Subscriptions (YS15)": {
                "definition": "",
                "examples": "",
            },
            "Laboratory Furniture Spares (YS16)": {
                "definition": "Replacement parts and accessories required for the upkeep, repair, and maintenance of laboratory furniture, ensuring continued functionality and safety.",
                "examples": "",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZVRP — Packing Materials
    # ──────────────────────────────────────────────────────────────────────
    "ZVRP": {
        "label": "Packing Materials - ZVRP",
        "override_rules": "",
        "categories": {
            "Primary Packaging (YS31)": {
                "definition": "The first layer of packaging that comes in direct contact with the product and is intended to contain, protect, and preserve it for use or consumption.",
                "examples": "Bottle for chemicals, blister strip for tablets, pouch for powder, ampoule for injectables & Etc",
            },
            "Secondary Packaging (YS33)": {
                "definition": "Packaging that groups one or more primary packages together to facilitate handling, storage, branding, or retail sale. It may also offer additional protection during distribution.",
                "examples": "Carton holding multiple bottles, shrink wrap around boxes, cardboard outer box for blister pac",
            },
            "Tertiary Packaging (YS34)": {
                "definition": "The outermost layer of packaging used for bulk handling, warehousing, and transportation of secondary packaged goods, typically not seen by the end consumer.",
                "examples": "Pallets, stretch wrap, large shipping crates, containerized packaging & Etc",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZANI — Animals
    # ──────────────────────────────────────────────────────────────────────
    "ZANI": {
        "label": "Animals - ZANI",
        "override_rules": "",
        "categories": {
            "Small Animals (YS42)": {
                "definition": "Non-rodent and rodent species of smaller body size commonly used in laboratory studies for safety, efficacy, and pharmacology research. Typically easier to handle, require less housing space, and are cost-effective for large study groups.",
                "examples": "Guinea Pigs,Hamsters,Mice,Rabbit,Rats",
            },
            "Large Animals (YS43)": {
                "definition": "Non-rodent species of larger body size used for translational research, surgical models, or regulatory toxicology studies when physiological similarity to humans is required. Usually require specialized housing and handling facilities.",
                "examples": "Dogs (beagle), pigs, goats, sheep, monkeys, horses",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  ZSTR — Stationery
    # ──────────────────────────────────────────────────────────────────────
    "ZSTR": {
        "label": "Stationery - ZSTR",
        "override_rules": "",
        "categories": {
            "Office & Administration Supplies (YS44)": {
                "definition": "Standard stationery items used for general office, administrative, and documentation purposes.",
                "examples": "Pens, notebooks, files, staplers & Etc",
            },
            "Customized & Special Purpose Supplies (YS45)": {
                "definition": "Stationery designed for specific functions or branded requirements, often custom-printed or specialized for certain processes.",
                "examples": "Company-branded letterheads, pre-printed forms, laboratory logbooks & Etc",
            },
        },
    },

    # ──────────────────────────────────────────────────────────────────────
    #  SERVICES — Services
    # ──────────────────────────────────────────────────────────────────────
    "SERVICES": {
        "label": "Services",
        "override_rules": "",
        "categories": {
            "Professional - Technical Services (YS46)": {
                "definition": "Processing charges,Agency commission,Site investigator payment,Clinical trial expenses,R&D services",
                "examples": "",
            },
            "Contingent Labour (YS47)": {
                "definition": "Contract Manpower Salary, Retainer/Consultants/Partner Salary, Overseas Employee Salary, Casual Manpower (Security/Housekeeping)",
                "examples": "",
            },
            "Marketing, Sales & Promotion Services (YS48)": {
                "definition": "Advertisement & brand promotion,Sales & promotion expense,Distribution charges",
                "examples": "",
            },
            "Logistics & Supply Chain Services (YS49)": {
                "definition": "Freight charges,Clearing charges",
                "examples": "",
            },
            "Travel & Accomodation Services (YS50)": {
                "definition": "Employee Transportation/ Travel, Accomodation for new joinee,",
                "examples": "",
            },
            "Facility Maintenance Services (YS51)": {
                "definition": "Maintenance, AMC, Engineering, Erection Commission",
                "examples": "",
            },
            "Training & Employee Welfare Services (YS52)": {
                "definition": "Team Outing, Car Lease, Trainings, Memberships",
                "examples": "",
            },
            "IT Support Services (YS53)": {
                "definition": "Computer software expenses",
                "examples": "",
            },
            "Finance & Banking Services (YS54)": {
                "definition": "Bank charges,Insurance charges,Rates and taxes",
                "examples": "",
            },
            "Administrative Services (YS55)": {
                "definition": "Canteen Snacks/ Tea & Beverages",
                "examples": "",
            },
            "Rental & Utilities (YS56)": {
                "definition": "Facility Rent",
                "examples": "",
            },
            "Special Categorization (Internal/Company-Specific) (YS58)": {
                "definition": "SYG Capex service, SYG Opex service",
                "examples": "",
            },
            "Job Work Services (YS28)": {
                "definition": "",
                "examples": "",
            },
            "Membership & Non-IT Subscriptions (YS29)": {
                "definition": "",
                "examples": "",
            },
        },
    },
}

# Convenience: list of all taxonomy keys with labels for the frontend dropdown
TAXONOMY_OPTIONS = [
    {"key": k, "label": v["label"]}
    for k, v in MATERIAL_TAXONOMIES.items()
]
