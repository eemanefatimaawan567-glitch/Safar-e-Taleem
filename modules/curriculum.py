"""
Safar-e-Taleem — Offline Learning Packets (Curriculum Content Engine)

Provides grade-level curriculum packs for families without digital devices
during hybrid/online school days. Content aligns with Pakistani federal board
curriculum (grades 1-10). Used by the principal to generate printable PDFs
and push WhatsApp/SMS/IVR summaries to unmatched families.
"""


# ---------------------------------------------------------
# CURRICULUM PACKS — sample weekly content per grade band
# ---------------------------------------------------------

CURRICULUM_PACKS = {
    "primary": {
        "title": "Primary Learning Packet (Grade 1-5)",
        "week": "Week 1",
        "level": "primary",
        "subjects": [
            {
                "name": "Mathematics",
                "topics": [
                    {
                        "title": "Addition & Subtraction (2-digit numbers)",
                        "content": (
                            "Step 1: Line up numbers by place value (ones under ones, tens under tens).\n"
                            "Step 2: Add or subtract starting from the ones column.\n"
                            "Step 3: Carry over (addition) or borrow (subtraction) when needed.\n\n"
                            "Example: 47 + 36 = ?\n"
                            "  Ones: 7 + 6 = 13 → write 3, carry 1\n"
                            "  Tens: 4 + 3 + 1 = 8\n"
                            "  Answer: 83"
                        ),
                    },
                    {
                        "title": "Multiplication Tables (2, 3, 4, 5)",
                        "content": (
                            "Practice chanting these tables aloud twice daily:\n"
                            "  2 × 1 = 2,  2 × 2 = 4,  2 × 3 = 6,  2 × 4 = 8,  2 × 5 = 10\n"
                            "  3 × 1 = 3,  3 × 2 = 6,  3 × 3 = 9,  3 × 4 = 12, 3 × 5 = 15\n"
                            "  4 × 1 = 4,  4 × 2 = 8,  4 × 3 = 12, 4 × 4 = 16, 4 × 5 = 20\n"
                            "  5 × 1 = 5,  5 × 2 = 10, 5 × 3 = 15, 5 × 4 = 20, 5 × 5 = 25"
                        ),
                    },
                ],
                "activities": [
                    "Draw a number line from 0 to 100 and jump by 2s, 5s, and 10s.",
                    "Use 20 small stones or buttons. Group them into sets of 3. Count how many groups and how many left over.",
                    "Play 'Shopkeeper': price 5 household items with tags under Rs 50. Calculate the total cost.",
                ],
                "assignments": [
                    "Solve 15 addition and 15 subtraction problems in your notebook.",
                    "Write multiplication tables of 2, 3, 4, and 5 — twice each.",
                    "Word problem: Ali has 34 mangoes. He gives 17 to his neighbour. How many are left?",
                ],
            },
            {
                "name": "Science",
                "topics": [
                    {
                        "title": "Parts of a Plant & What Plants Need to Grow",
                        "content": (
                            "Every plant has 5 main parts:\n"
                            "  1. Roots — absorb water and nutrients from the soil.\n"
                            "  2. Stem — carries water from roots to leaves; holds the plant upright.\n"
                            "  3. Leaves — make food using sunlight (photosynthesis).\n"
                            "  4. Flowers — produce seeds for new plants.\n"
                            "  5. Fruit — protects the seeds inside.\n\n"
                            "Plants need 3 things to grow: sunlight, water, and air."
                        ),
                    },
                ],
                "activities": [
                    "Take a small plant from your garden or a neighbour's. Draw and label all 5 parts.",
                    "Plant a bean seed in a cup with wet cotton. Observe it daily for 7 days and draw what you see.",
                ],
                "assignments": [
                    "Draw a plant and label: roots, stem, leaves, flower, fruit.",
                    "Answer in 2 sentences: Why do plants need sunlight?",
                ],
            },
            {
                "name": "Urdu",
                "topics": [
                    {
                        "title": "Hamari Zaban — Urdu Reading & Writing",
                        "content": (
                            "پڑھیں: 'میرا پاکستان'\n"
                            "میرا وطن پاکستان ہے۔ یہ ایک خوبصورت ملک ہے۔\n"
                            "اس کے چار صوبے ہیں: پنجاب، سندھ، بلوچستان اور خیبر پختونخوا۔\n"
                            "ہمارا قومی پھول چمیلی ہے۔ قومی کھیل ہاکی ہے۔\n\n"
                            "Writing Practice: Copy the above passage in your notebook twice."
                        ),
                    },
                ],
                "activities": [
                    "Read the passage aloud 3 times. Ask a family member to listen.",
                    "Find 5 new Urdu words in a newspaper. Write their meanings.",
                ],
                "assignments": [
                    "Copy the passage twice in your Urdu notebook.",
                    "Write 5 sentences about your school in Urdu.",
                ],
            },
            {
                "name": "English",
                "topics": [
                    {
                        "title": "My Daily Routine — Present Simple Tense",
                        "content": (
                            "Read the passage:\n"
                            "'I wake up at 6 o'clock. I brush my teeth and take a bath.\n"
                            "I eat breakfast at 7 o'clock. I go to school at 7:30.\n"
                            "I come home at 2 o'clock. I eat lunch and do my homework.\n"
                            "I play with my friends in the evening. I sleep at 9 o'clock.'\n\n"
                            "Grammar Rule: We use Present Simple for habits and daily routines.\n"
                            "  I eat. / She eats. / They play. / He plays."
                        ),
                    },
                ],
                "activities": [
                    "Write 10 sentences about YOUR daily routine using the same pattern.",
                    "Underline all the verbs (action words) in the passage above.",
                ],
                "assignments": [
                    "Write a paragraph: 'My School Day' (at least 8 sentences).",
                    "Fill in the blanks: She ___ (go/goes) to school. They ___ (eat/eats) lunch.",
                ],
            },
        ],
    },

    "middle": {
        "title": "Middle School Learning Packet (Grade 6-8)",
        "week": "Week 1",
        "level": "middle",
        "subjects": [
            {
                "name": "Mathematics",
                "topics": [
                    {
                        "title": "Algebraic Expressions & Simplification",
                        "content": (
                            "An algebraic expression uses letters (variables) and numbers.\n"
                            "  Example: 3x + 5 means '3 times some number, plus 5'.\n\n"
                            "Simplifying: combine like terms.\n"
                            "  2x + 3x = 5x   (add the coefficients)\n"
                            "  4y - y = 3y    (subtract)\n"
                            "  2a + 3b + a - b = 3a + 2b   (group like terms)\n\n"
                            "Evaluating: replace the variable with a number.\n"
                            "  If x = 4, then 3x + 5 = 3(4) + 5 = 12 + 5 = 17"
                        ),
                    },
                    {
                        "title": "Ratio & Proportion",
                        "content": (
                            "A ratio compares two quantities: 3:5 means 'for every 3 of A, there are 5 of B'.\n"
                            "  Example: In a class of 40, the boys:girls ratio is 3:2.\n"
                            "  Total parts = 3 + 2 = 5. Each part = 40 / 5 = 8.\n"
                            "  Boys = 3 × 8 = 24. Girls = 2 × 8 = 16.\n\n"
                            "Proportion: two equal ratios.  2/4 = 3/6  (cross multiply to check: 2×6 = 4×3)."
                        ),
                    },
                ],
                "activities": [
                    "Find the ratio of boys to girls in your household. Express it in simplest form.",
                    "If 3 notebooks cost Rs 120, use proportion to find the cost of 7 notebooks.",
                ],
                "assignments": [
                    "Simplify: (a) 5x + 2x - 3x   (b) 4a + 7b - 2a + 3b",
                    "Solve: If 5 workers can build a wall in 12 days, how many days will 10 workers take?",
                    "Evaluate 2x² + 3x - 1 when x = -2.",
                ],
            },
            {
                "name": "Science",
                "topics": [
                    {
                        "title": "The Human Digestive System",
                        "content": (
                            "Digestion is the process of breaking food into nutrients the body can absorb.\n\n"
                            "Path of food:\n"
                            "  Mouth → Oesophagus (food pipe) → Stomach → Small Intestine → Large Intestine\n\n"
                            "Key organs:\n"
                            "  • Mouth: teeth chew food, saliva starts breaking it down.\n"
                            "  • Stomach: acid and enzymes break food into a paste (chyme).\n"
                            "  • Small intestine: nutrients are absorbed into the blood through villi.\n"
                            "  • Large intestine: water is absorbed; waste becomes faeces.\n"
                            "  • Liver: produces bile (stored in gallbladder) to digest fats."
                        ),
                    },
                ],
                "activities": [
                    "Draw a labelled diagram of the digestive system (use a textbook as reference).",
                    "Track what you eat for one day. Write where each food type is digested.",
                ],
                "assignments": [
                    "Label: mouth, oesophagus, stomach, liver, small intestine, large intestine.",
                    "Explain in 3-4 sentences: What happens to food in the stomach?",
                ],
            },
            {
                "name": "English",
                "topics": [
                    {
                        "title": "Parts of Speech — Complete Review",
                        "content": (
                            "8 Parts of Speech:\n"
                            "  1. Noun — a person, place, thing, or idea (Lahore, book, happiness)\n"
                            "  2. Pronoun — replaces a noun (he, she, it, they)\n"
                            "  3. Verb — an action or state (run, is, think)\n"
                            "  4. Adjective — describes a noun (beautiful, tall, blue)\n"
                            "  5. Adverb — describes a verb (quickly, very, well)\n"
                            "  6. Preposition — shows position/time (in, on, under, before)\n"
                            "  7. Conjunction — joins words/clauses (and, but, because)\n"
                            "  8. Interjection — expresses emotion (Wow! Oh! Ouch!)"
                        ),
                    },
                ],
                "activities": [
                    "Take a newspaper article and underline one example of each part of speech.",
                    "Write 5 sentences, each containing at least one adjective and one adverb.",
                ],
                "assignments": [
                    "Identify all 8 parts of speech in: 'The tall boy ran quickly across the busy street.'",
                    "Write a 100-word paragraph about your neighbourhood using at least 4 adjectives and 3 adverbs.",
                ],
            },
            {
                "name": "Urdu",
                "topics": [
                    {
                        "title": "Nazm: 'پاکستان' — Allama Iqbal",
                        "content": (
                            "نظم (حصہ):\n"
                            "سارے جہاں سے اچھا ہندوستاں ہمارا\n"
                            "ہم بلبلیں ہیں اس کی، یہ گلستاں ہمارا\n\n"
                            "خلاصہ: شاعر اپنے وطن سے محبت کا اظہار کرتا ہے۔\n"
                            "وہ کہتا ہے کہ پورا جہاں خوبصورت ہے لیکن ہمارا وطن سب سے اچھا ہے۔\n\n"
                            "Vocabulary:\n"
                            "  جہاں = دنیا    |    گلستاں = باغ\n"
                            "  بلبلیں = پرندے  |    وطن = ملک"
                        ),
                    },
                ],
                "activities": [
                    "Read the nazm aloud 3 times with correct pronunciation.",
                    "Memorise the first 4 lines.",
                ],
                "assignments": [
                    "Write the nazm from memory in your notebook.",
                    "Answer: شاعر اپنے وطن کو کیا کہتا ہے؟ (2 sentences)",
                ],
            },
        ],
    },

    "secondary": {
        "title": "Secondary Learning Packet (Grade 9-10)",
        "week": "Week 1",
        "level": "secondary",
        "subjects": [
            {
                "name": "Mathematics",
                "topics": [
                    {
                        "title": "Quadratic Equations",
                        "content": (
                            "Standard form: ax² + bx + c = 0\n\n"
                            "Quadratic Formula:  x = (-b ± √(b² - 4ac)) / 2a\n\n"
                            "Example: Solve x² - 5x + 6 = 0\n"
                            "  a=1, b=-5, c=6\n"
                            "  Discriminant = (-5)² - 4(1)(6) = 25 - 24 = 1\n"
                            "  x = (5 ± √1) / 2 = (5 ± 1) / 2\n"
                            "  x = 3  or  x = 2\n\n"
                            "Factoring method: x² - 5x + 6 = (x-2)(x-3) = 0 → x = 2 or x = 3"
                        ),
                    },
                    {
                        "title": "Coordinate Geometry — Distance & Midpoint",
                        "content": (
                            "Distance between A(x₁,y₁) and B(x₂,y₂):\n"
                            "  d = √((x₂-x₁)² + (y₂-y₁)²)\n\n"
                            "Midpoint of AB:\n"
                            "  M = ((x₁+x₂)/2, (y₁+y₂)/2)\n\n"
                            "Example: A(1,2) and B(5,6)\n"
                            "  Distance = √((5-1)² + (6-2)²) = √(16+16) = √32 ≈ 5.66\n"
                            "  Midpoint = ((1+5)/2, (2+6)/2) = (3, 4)"
                        ),
                    },
                ],
                "activities": [
                    "Plot 5 points on graph paper. Calculate distances between each pair.",
                    "Solve 5 quadratic equations using both the formula and factoring methods.",
                ],
                "assignments": [
                    "Solve: (a) x² - 7x + 12 = 0   (b) 2x² + 3x - 2 = 0   (c) x² + 4x + 4 = 0",
                    "Find the distance and midpoint between P(3, 7) and Q(8, 1).",
                ],
            },
            {
                "name": "Physics",
                "topics": [
                    {
                        "title": "Newton's Three Laws of Motion",
                        "content": (
                            "1st Law (Inertia): An object stays at rest or moves at constant velocity\n"
                            "  unless a net force acts on it.\n"
                            "  Example: A book on a table stays there until you push it.\n\n"
                            "2nd Law: F = ma  (Force = mass × acceleration)\n"
                            "  Example: A 2 kg ball pushed with 10 N force accelerates at a = F/m = 5 m/s².\n\n"
                            "3rd Law: Every action has an equal and opposite reaction.\n"
                            "  Example: When you jump, your feet push the ground down; the ground pushes you up."
                        ),
                    },
                ],
                "activities": [
                    "Give 2 real-life examples of each of Newton's three laws from your daily routine.",
                    "Calculate: A 1500 kg car accelerates at 3 m/s². What is the engine force?",
                ],
                "assignments": [
                    "State and explain Newton's three laws with one example each.",
                    "Numerical: A 5 kg object has a force of 20 N applied. Find acceleration. Then find\n"
                    "  the velocity after 4 seconds (assume starting from rest).",
                ],
            },
            {
                "name": "Chemistry",
                "topics": [
                    {
                        "title": "Periodic Table — Periods, Groups & Trends",
                        "content": (
                            "The periodic table arranges elements by increasing atomic number.\n\n"
                            "Periods (rows): 7 periods. Period number = number of electron shells.\n"
                            "Groups (columns): 18 groups. Elements in the same group have similar properties.\n\n"
                            "Key trends:\n"
                            "  • Atomic size: increases down a group, decreases across a period.\n"
                            "  • Metallic character: increases down a group, decreases across a period.\n"
                            "  • Electronegativity: decreases down a group, increases across a period."
                        ),
                    },
                ],
                "activities": [
                    "Draw a simplified periodic table showing the first 20 elements.",
                    "Predict: Is sodium (Na) more or less reactive than potassium (K)? Explain using trends.",
                ],
                "assignments": [
                    "Explain why fluorine is more electronegative than iodine.",
                    "Write the electronic configuration of the first 10 elements.",
                ],
            },
            {
                "name": "English",
                "topics": [
                    {
                        "title": "Reported Speech (Direct & Indirect)",
                        "content": (
                            "Direct speech: He said, 'I am going to school.'\n"
                            "Indirect (reported) speech: He said that he was going to school.\n\n"
                            "Tense changes when reporting:\n"
                            "  Present Simple → Past Simple:  'I like tea' → He said he liked tea.\n"
                            "  Present Continuous → Past Continuous:  'I am reading' → She said she was reading.\n"
                            "  Past Simple → Past Perfect:  'I finished it' → He said he had finished it.\n"
                            "  Will → Would:  'I will come' → She said she would come."
                        ),
                    },
                ],
                "activities": [
                    "Listen to a 5-minute conversation. Write down 5 sentences in reported speech.",
                    "Convert a short newspaper interview from direct to indirect speech.",
                ],
                "assignments": [
                    "Convert 10 sentences from direct to indirect speech.",
                    "Write a short dialogue (8 lines) and then rewrite it as a reported paragraph.",
                ],
            },
        ],
    },
}


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def get_pack(level):
    """Get a single curriculum pack by level ('primary', 'middle', 'secondary')."""
    return CURRICULUM_PACKS.get(level)


def get_all_packs():
    """Get all curriculum packs as a list of summary dicts."""
    return [
        {"level": level, "title": data["title"], "week": data["week"]}
        for level, data in CURRICULUM_PACKS.items()
    ]


def get_unmatched_family_count(all_parents):
    """Count families without a device who aren't matched to a study pod host."""
    from modules.commute_engine import form_study_pods
    _, unmatched = form_study_pods(all_parents)
    return len(unmatched)
