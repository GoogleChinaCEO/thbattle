# -*- coding: utf-8 -*-
from __future__ import absolute_import

# -- stdlib --
# -- third party --
# -- own --
from game.autoenv import EventHandler, Game
from thb.actions import ActionStage, AskForCard, DistributeCards, DrawCardStage, DrawCards
from thb.actions import GenericAction, PlayerTurn, Reforge, UserAction, migrate_cards
from thb.actions import random_choose_card, ttags, user_choose_cards, user_choose_players
from thb.cards import Heal, PhysicalCard, Skill, t_None, t_Self
from thb.characters.baseclasses import Character, register_character_to


# -- code --
class MiracleHeal(Heal):
    pass


class MiracleAction(UserAction):
    def apply_action(self):
        tgt = self.target
        g = Game.getgame()
        g.process_action(DrawCards(tgt, 1))

        ttags(tgt)['miracle_times'] += 1

        if ttags(tgt)['miracle_times'] == 3:
            candidates = [p for p in g.players if not p.dead and p.life < p.maxlife]
            if candidates:
                beneficiery, = user_choose_players(self, tgt, candidates) or (None,)
                if beneficiery:
                    g.process_action(MiracleHeal(tgt, beneficiery))

        return True

    def choose_player_target(self, tl):
        return tl[-1:], bool(tl)

    def cond(self, cl):
        return True

    def is_valid(self):
        tgt = self.target
        return len(self.associated_card.associated_cards) == ttags(tgt)['miracle_times'] + 1


class Miracle(Skill):
    associated_action = MiracleAction
    skill_category = ('character', 'active')
    target = t_Self
    usage = 'drop'

    def check(self):
        cl = self.associated_cards
        return cl and all(
            c.resides_in is not None and
            c.resides_in.type in (
                'cards', 'showncards', 'equips'
            ) for c in self.associated_cards
        )


class SanaeFaithCollectCardAction(GenericAction):
    card_usage = 'handover'
    no_reveal = True

    def apply_action(self):
        src, tgt = self.source, self.target
        cards = user_choose_cards(self, tgt, ('cards', 'showncards'))
        c = cards[0] if cards else random_choose_card([tgt.cards, tgt.showncards])
        src.reveal(c)
        migrate_cards([c], src.cards)

        return True

    def cond(self, cl):
        return len(cl) == 1 and \
            cl[0].resides_in.type in ('cards', 'showncards') and \
            not cl[0].is_card(Skill)


class SanaeFaithReturnCardAction(GenericAction):
    card_usage = 'handover'
    no_reveal = True

    def apply_action(self):
        src, tgt = self.source, self.target
        cards = user_choose_cards(self, src, ('cards', 'showncards', 'equips'))
        c = cards[0] if cards else random_choose_card([src.cards, src.showncards, src.equips])
        if not c:
            return False

        tgt.reveal(c)
        migrate_cards([c], tgt.cards)

        return True

    def cond(self, cl):
        return len(cl) == 1 and not cl[0].is_card(Skill)


class SanaeFaithAction(UserAction):
    def apply_action(self):
        src = self.source
        tl = self.target_list
        g = Game.getgame()

        for p in tl:
            g.process_action(SanaeFaithCollectCardAction(src, p))

        g.deck.shuffle(src.cards)

        for p in tl:
            g.process_action(SanaeFaithReturnCardAction(src, p))

        ttags(src)['faith'] = True

        return True

    def is_valid(self):
        src = self.source
        return not ttags(src)['faith']


class SanaeFaith(Skill):
    associated_action = SanaeFaithAction
    skill_category = ('character', 'active')
    usage = 'launch'

    @staticmethod
    def target(g, source, tl):
        tl = [t for t in tl if not t.dead and (t.cards or t.showncards)]
        try:
            tl.remove(source)
        except ValueError:
            pass

        return (tl[:2], bool(len(tl)))

    def check(self):
        return not self.associated_cards


class SanaeFaithKOF(Skill):
    associated_action = None
    skill_category = ('character', 'passive')
    target = t_None


class SanaeFaithKOFDrawCards(DrawCards):
    pass


class SanaeFaithKOFHandler(EventHandler):
    interested = ('card_migration',)

    def handle(self, evt_type, arg):
        if evt_type == 'card_migration':
            act, cards, _from, to, _ = arg
            if isinstance(act, (DistributeCards, DrawCardStage)):
                return arg

            if to is None or not to.owner:
                return arg

            if to.type not in ('cards', 'showncards', 'equips'):
                return arg

            if _from is not None and _from.owner is to.owner:
                return arg

            g = Game.getgame()
            a, b = g.players

            if not a.has_skill(SanaeFaithKOF):
                a, b = b, a

            if not a.has_skill(SanaeFaithKOF):
                return arg

            if b is not to.owner:
                return arg

            turn = PlayerTurn.get_current()
            if not turn:
                return arg

            stage = turn.current_stage
            if stage.target is not b or not isinstance(stage, ActionStage):
                return arg

            g = Game.getgame()

            g.process_action(SanaeFaithKOFDrawCards(a, 1))

        return arg


class GodDescendant(Skill):
    associated_action = None
    skill_category = ('character', 'passive')


class GodDescendantEffect(UserAction):
    def __init__(self, source, target, target_list, card):
        self.source      = source
        self.target      = target
        self.target_list = target_list
        self.card        = card

    def apply_action(self):
        g = Game.getgame()
        src, tgt, tl = self.source, self.target, self.target_list
        g.process_action(Reforge(src, tgt, self.card))
        assert tgt in tl
        tl.remove(tgt)
        return True


class GodDescendantAction(AskForCard):
    card_usage = 'reforge'

    def __init__(self, target, target_list):
        AskForCard.__init__(self, target, target, PhysicalCard, ('cards', 'showncards', 'equips'))
        self.target_list = target_list

    def process_card(self, c):
        g = Game.getgame()
        return g.process_action(GodDescendantEffect(self.source, self.target, self.target_list, c))


class GodDescendantHandler(EventHandler):
    interested = ('choose_target',)
    execute_before = ('MaidenCostumeHandler', )

    def handle(self, evt_type, arg):
        if evt_type == 'choose_target':
            act, tl = arg
            if 'group_effect' not in act.card.category:
                return arg

            g = Game.getgame()
            for tgt in tl:
                if not tgt.has_skill(GodDescendant):
                    continue

                g.process_action(GodDescendantAction(tgt, tl))

        return arg

    def cond(self, cl):
        return len(cl) == 1


@register_character_to('common', '-kof')
class Sanae(Character):
    skills = [Miracle, SanaeFaith, GodDescendant]
    eventhandlers_required = [GodDescendantHandler]
    maxlife = 3


@register_character_to('kof')
class SanaeKOF(Character):
    skills = [Miracle, SanaeFaithKOF, GodDescendant]
    eventhandlers_required = [SanaeFaithKOFHandler, GodDescendantHandler]
    maxlife = 3
