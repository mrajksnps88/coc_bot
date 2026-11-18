from __future__ import annotations
import logging
from transitions import Machine

logger = logging.getLogger(__name__)

class BotStateMachine:
    states = [
        'loading', 'main_village', 'collect_resources', 
        'train_troops', 'find_match', 'battle', 
        'battle_end', 'idle', 'disconnected', 'upgrade_walls'
    ]
    
    def __init__(self):
        self.machine = Machine(
            model=self,
            states=BotStateMachine.states,
            initial='loading',
            auto_transitions=False,
            send_event=True
        )
        self._define_transitions()
        self._stats = {'state_changes': 0, 'errors': 0}
        
    def _define_transitions(self):
        # From Loading
        self.machine.add_transition('home_detected', ['loading', 'disconnected'], 'main_village')
        
        # From Main Village
        self.machine.add_transition('collectors_ready', 'main_village', 'collect_resources')
        self.machine.add_transition('army_incomplete', 'main_village', 'train_troops')
        self.machine.add_transition('army_ready', 'main_village', 'find_match')
        self.machine.add_transition('excess_loot', 'main_village', 'upgrade_walls')
        self.machine.add_transition('nothing_to_do', 'main_village', 'idle')
        
        # Returning to Main Village
        self.machine.add_transition('collection_done', 'collect_resources', 'main_village')
        self.machine.add_transition('training_started', 'train_troops', 'main_village')
        self.machine.add_transition('search_cancelled', 'find_match', 'main_village')
        self.machine.add_transition('return_home', 'battle_end', 'main_village')
        self.machine.add_transition('wall_upgrade_done', 'upgrade_walls', 'main_village')
        self.machine.add_transition('wake_up', 'idle', 'main_village')
        
        # Battle flow
        self.machine.add_transition('match_found', 'find_match', 'battle')
        self.machine.add_transition('battle_over', 'battle', 'battle_end')
        
        # Disconnections
        self.machine.add_transition('connection_lost', '*', 'disconnected')
        self.machine.add_transition('reconnecting', 'disconnected', 'loading')
        
    # State Enter Callbacks
    def on_enter_loading(self, event): logger.info("State: LOADING")
    def on_enter_main_village(self, event): logger.info("State: MAIN_VILLAGE")
    def on_enter_collect_resources(self, event): logger.info("State: COLLECT_RESOURCES")
    def on_enter_train_troops(self, event): logger.info("State: TRAIN_TROOPS")
    def on_enter_find_match(self, event): logger.info("State: FIND_MATCH")
    def on_enter_battle(self, event): logger.info("State: BATTLE")
    def on_enter_battle_end(self, event): logger.info("State: BATTLE_END")
    def on_enter_upgrade_walls(self, event): logger.info("State: UPGRADE_WALLS")
    def on_enter_idle(self, event): logger.info("State: IDLE")
    def on_enter_disconnected(self, event): logger.info("State: DISCONNECTED")
    
    @property
    def current(self) -> str:
        return self.state
        
    @property
    def stats(self) -> dict:
        return self._stats
