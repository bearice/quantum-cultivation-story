# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chinese language creative writing project called "GPT Story Maker" - a light novel/web novel with a complex multi-dimensional storyline. The protagonist Lin Wanwan is a medical student who transmigrates into a cultivation world and develops the ability to summon multiple versions of herself from parallel realities through quantum superposition states.

## Repository Structure

```
├── Vol1/          # Detailed plot design for chapters 1-20
├── Vol2/          # Detailed plot design for chapters 21-40  
├── Vol3/          # Detailed plot design for chapters 41-60
├── Vol4/          # (Reserved for chapters 61-80)
├── Vol5/          # (Reserved for chapters 81-100)
└── 设定/           # Story settings and design documents
    ├── 写作规范.md       # Centralized writing standards and style guidelines (PRIORITY)
    ├── 大纲.md          # Master outline with world-building and character designs
    ├── 人格机制设定.md   # Personality mechanism settings
    ├── 人格图鉴.md       # Character personality profiles  
    ├── 人物档案.md       # Character development tracking
    ├── 伏笔追踪表.md     # Foreshadowing tracking table
    └── 背景势力设定.md   # Faction and power structure definitions
```

## Story Architecture

**Core Concept**: Quantum superposition mechanics where the protagonist exists in multiple states simultaneously, manifesting as up to 42 different personalities/versions of herself.

**Key Elements**:
- Multi-dimensional personality system based on quantum mechanics
- Cultivation world setting with modern scientific knowledge integration
- Progressive power system tied to cultivation realms (Qi Refinement → Foundation Building → Golden Core → Nascent Soul)
- Philosophical themes around identity, choice, and the nature of existence
- The number "42" as a central motif (reference to Hitchhiker's Guide to the Galaxy)

## Core Characters

- **Lin Wanwan (Original)**: Medical student protagonist with social anxiety and hoarding tendencies
- **Personality #1**: Yandere version from dating sim world
- **Personality #2**: Foodie version from culinary world  
- **Personality #7**: Mathematician version focused on calculations
- **Personality #21**: 5-year-old child version representing innocence
- **Personality #35**: Lawyer version focused on justice
- **Personality #42**: The "Answer Keeper" who knows ultimate truths but speaks in riddles
- **System 009**: Malfunctioning cultivation system with multiple personality disorder
- **The Unifier (Chen Yi)**: Main antagonist who seeks to eliminate all possibilities except one

## Writing Guidelines

**Language**: All content is in Chinese (Simplified)
**Genre**: Light novel/web novel with elements of:
- Xianxia (Cultivation fiction)
- Comedy/slice of life
- Science fiction concepts
- Philosophical exploration
- Action/adventure

**Tone**: Balances humor with deeper philosophical themes. Contains both lighthearted personality interactions and serious existential questions.

## Document Hierarchy and Management

**Authority Structure**:
- **设定/写作规范.md** - Centralized writing standards and style guidelines (PRIMARY reference for all writing rules)
- **设定/大纲.md** - Master story outline and world-building (takes precedence for plot/setting conflicts)  
- **设定/人格图鉴.md** - Character personality profiles with flexible management
- **设定/伏笔追踪表.md** - Plot thread and foreshadowing tracking across all story arcs
- **设定/背景势力设定.md** - Faction relationships and power structures
- **Vol directories** - Detailed chapter-by-chapter breakdowns

**Consistency Rules**:
- All story documents are in Markdown format  
- Character names and terminology must remain consistent across all files
- Writing standards and style: 设定/写作规范.md takes precedence
- Plot and world-building conflicts: 设定/大纲.md takes precedence
- New personality additions should immediately update both 人格图鉴.md and 伏笔追踪表.md
- Timeline discrepancies should be resolved using the outline's chapter structure

## Key Story Mechanics

**Personality System**: 
- Core personalities: #1 (Yandere), #2 (Foodie), #7 (Mathematician), #21 (Child), #35 (Lawyer), #42 (Answer Keeper)
- Each personality represents a different "way of understanding the universe"
- Power scaling tied to cultivation realms with realistic multipliers (1.8x-8x max)
- Internal meeting space allows personalities to collaborate in accelerated time

**Plot Structure**:
- 5 volumes of 20 chapters each (100 chapters total)
- Quantum mechanics integrated with cultivation world logic
- Philosophical themes around identity, choice, and observer effect
- Multiple antagonist factions with different ideologies

## AI-Assisted Workflow

This project uses a specialized AI agent for comprehensive quality assurance:

**Available Agent**:
- `comprehensive-story-checker`: Unified quality validation system that performs:
  - Settings compliance verification (against 设定/大纲.md and 设定/写作规范.md)
  - Character authenticity checking (dialogue consistency, personality voices)
  - Narrative coherence validation (scene transitions, plot logic)
  - Humor/philosophy balance assessment

**Quality Assurance Process**:
1. Generate/modify story content
2. Review and request plot/character adjustments  
3. Use comprehensive-story-checker for complete validation
4. Agent automatically reads latest standards from 设定/写作规范.md before each check

## Development Notes

This is a pure creative writing project with no executable code. When working with these files, focus on:
- Maintaining narrative consistency across all setting documents
- Preserving distinct character voices for each personality
- Tracking plot threads and foreshadowing elements using 伏笔追踪表.md
- Ensuring philosophical themes remain coherent throughout the story
- Balancing humor with deeper existential questions
- You should always use chinese in the main text
- Update character lists as story develops
- You need to control each chapter to above 2000 words
- Pay attention to the plot's pacing, maintain appropriate suspense between chapters, and arouse the reader's desire to read
- **数字使用规范**：人格编号统一使用中文数字（小一、小二、小七、二十一号、三十五号、四十二号），不使用阿拉伯数字

## Writing Standards Reference

**⚠️ CRITICAL**: Always refer to `设定/写作规范.md` for complete and current writing standards. Key points:

- **System009 Dialogue Format**: 系统009【对话内容】 (no quotation marks)
- **Character Nicknames**: Other characters may call system "系统" or "009" in dialogue  
- **Personality Numbers**: Use Chinese numerals (小一、小二、小七、二十一号、三十五号、四十二号)
- **Language Rules**: 
  - Lin Wanwan: Modern terms internally, cultivation terms externally
  - Cultivation world characters: Strict Daoist terminology only
  - Personality #7: Scientific terms with cultivation physics vocabulary
- **Chapter Requirements**: Minimum 2000 characters, avoid unnecessary metadata
- **Title Diversity**: Avoid repetitive "XX的XX" format, use varied styles

**Before any writing/editing task**: Read 设定/写作规范.md for latest standards
