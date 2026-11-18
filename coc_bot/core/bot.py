from __future__ import annotations
import logging
from pathlib import Path
import time

from coc_bot.config.settings import BotSettings
from coc_bot.modules.capture.adb_capture import ADBCapture
from coc_bot.modules.capture.screen_capture import ScreenCapture
from coc_bot.modules.input.adb_input import ADBInput
from coc_bot.modules.input.windows_input import WindowsInput
from coc_bot.modules.vision.template_matcher import TemplateMatcher
from coc_bot.modules.vision.color_detector import ColorDetector
from coc_bot.modules.vision.ocr_reader import OCRReader
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.modules.decision.engine import DecisionEngine
from coc_bot.modules.decision.strategies.collect_strategy import CollectStrategy
from coc_bot.modules.decision.strategies.idle_strategy import IdleStrategy
from coc_bot.modules.decision.strategies.train_strategy import TrainStrategy
from coc_bot.modules.decision.strategies.attack_strategy import AttackStrategy
from coc_bot.core.game_loop import GameLoop
from coc_bot.utils.adb_utils import ADBConnection

logger = logging.getLogger(__name__)

class Bot:
    """Main bot class. Wires all modules and manages lifecycle."""
    
    def __init__(self, settings: BotSettings | None = None, 
                 config_path: Path | None = None):
        self.settings = settings or BotSettings()
        
        # 1. Setup Connection & Capture
        self.adb = ADBConnection(self.settings.adb)
        self.capturer = ADBCapture(self.settings.adb, self.adb)
        # Note: could conditionally use ScreenCapture if ADB fails or configured
        
        # 2. Setup Input
        self.input_handler = ADBInput(self.adb, self.settings.timing)
        self.input_handler.dry_run = self.settings.dry_run
        
        # 3. Setup Vision
        self.template_matcher = TemplateMatcher(
            template_dir=self.settings.vision.template_dir,
            threshold=self.settings.vision.match_threshold,
            grayscale=self.settings.vision.grayscale
        )
        self.color_detector = ColorDetector()
        self.ocr_reader = OCRReader() if not self.settings.dry_run else None # Lazy load
        from coc_bot.modules.decision.strategies.collect_strategy import CollectStrategy
        from coc_bot.modules.decision.strategies.idle_strategy import IdleStrategy
        from coc_bot.modules.decision.strategies.train_strategy import TrainStrategy
        from coc_bot.modules.decision.strategies.attack_strategy import AttackStrategy
        from coc_bot.modules.decision.strategies.main_village_strategy import MainVillageStrategy
        from coc_bot.modules.decision.strategies.upgrade_walls_strategy import UpgradeWallsStrategy
        from coc_bot.modules.decision.strategies.disconnected_strategy import DisconnectedStrategy
        
        self.detector = GameDetector(
            template_matcher=self.template_matcher,
            color_detector=self.color_detector,
            ocr_reader=self.ocr_reader
        )
        
        # 4. Setup State & Decision
        self.state_machine = BotStateMachine()
        self.decision_engine = DecisionEngine(self.detector, self.settings)
        
        # Register strategies
        self.decision_engine.register_strategy('main_village', MainVillageStrategy(self.settings))
        self.decision_engine.register_strategy('collect_resources', CollectStrategy())
        self.decision_engine.register_strategy('idle', IdleStrategy())
        self.decision_engine.register_strategy('train_troops', TrainStrategy(self.settings))
        self.decision_engine.register_strategy('upgrade_walls', UpgradeWallsStrategy(self.settings))
        self.decision_engine.register_strategy('disconnected', DisconnectedStrategy())
        
        attack_strategy = AttackStrategy(self.settings)
        self.decision_engine.register_strategy('find_match', attack_strategy)
        self.decision_engine.register_strategy('battle', attack_strategy)
        self.decision_engine.register_strategy('battle_end', attack_strategy)
        # 5. Setup Game Loop
        self.game_loop = GameLoop(
            capturer=self.capturer,
            detector=self.detector,
            decision_engine=self.decision_engine,
            input_handler=self.input_handler,
            state_machine=self.state_machine,
            settings=self.settings
        )
        
    def start(self) -> None:
        """Start the bot."""
        logger.info("Bot starting up...")
        if self.ocr_reader:
            self.ocr_reader.preload()
            
        # Connect to emulator
        try:
            self.adb.connect()
        except Exception as e:
            logger.error(f"Failed to connect to ADB device: {e}")
            return
            
        if not self.adb.is_connected():
            logger.error("Failed to connect to ADB device. Ensure emulator is running.")
            return
            
        self.capturer.connect()
        
        # Load templates
        templates_loaded = self.template_matcher.load_templates_from_dir(
            self.settings.vision.template_dir
        )
        if templates_loaded == 0:
            logger.warning("No templates loaded. Bot will not function correctly.")
            
        logger.info("Bot initialized. Starting game loop.")
        self.game_loop.start()
        
    def stop(self) -> None:
        """Gracefully stop the bot."""
        logger.info("Stopping bot...")
        self.game_loop.stop()
        self.capturer.disconnect()
        
    def pause(self) -> None:
        self.game_loop.pause()
        
    def resume(self) -> None:
        self.game_loop.resume()
        
    @property
    def status(self) -> dict:
        return {
            'state': self.state_machine.current,
            'dry_run': self.settings.dry_run,
            'stats': self.state_machine.stats
        }
