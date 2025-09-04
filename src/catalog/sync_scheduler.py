"""
Планировщик синхронизации товаров каждые 12 часов
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from utils.logger import app_logger
from .products_cache_manager import ProductsCacheManager


class ProductSyncScheduler:
    """
    Планировщик автоматической синхронизации товаров из МойСклад
    
    Функции:
    - Автоматическая синхронизация каждые 12 часов
    - Первоначальная синхронизация при запуске
    - Обработка ошибок и повторные попытки
    - Статистика синхронизации
    """
    
    def __init__(self):
        """Инициализация планировщика синхронизации"""
        self.cache_manager = ProductsCacheManager()
        self.sync_interval_hours = 12
        self.retry_interval_minutes = 30
        self.max_retries = 3
        
        # Флаги состояния
        self.is_running = False
        self.sync_task: Optional[asyncio.Task] = None
        self.last_sync_result = None
        
        app_logger.info("ProductSyncScheduler инициализирован")
    
    async def start(self, initial_sync: bool = True):
        """
        Запускает планировщик синхронизации
        
        Args:
            initial_sync: Выполнить ли первоначальную синхронизацию
        """
        if self.is_running:
            app_logger.warning("Планировщик уже запущен")
            return
        
        self.is_running = True
        app_logger.info("Запускаем планировщик синхронизации товаров")
        
        # Первоначальная синхронизация при запуске
        if initial_sync:
            app_logger.info("Выполняем первоначальную синхронизацию товаров")
            await self._perform_sync_with_retry()
        
        # Запускаем фоновую задачу планировщика
        self.sync_task = asyncio.create_task(self._scheduler_loop())
        
        app_logger.info(f"Планировщик запущен (синхронизация каждые {self.sync_interval_hours} часов)")
    
    async def stop(self):
        """Останавливает планировщик синхронизации"""
        if not self.is_running:
            return
        
        app_logger.info("Останавливаем планировщик синхронизации")
        self.is_running = False
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        app_logger.info("Планировщик остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика синхронизации"""
        try:
            while self.is_running:
                # Вычисляем время до следующей синхронизации
                next_sync_time = self._calculate_next_sync_time()
                sleep_seconds = (next_sync_time - datetime.now()).total_seconds()
                
                if sleep_seconds > 0:
                    app_logger.info(f"Следующая синхронизация через {sleep_seconds/3600:.1f} часов в {next_sync_time.strftime('%H:%M:%S')}")
                    
                    # Ждем с проверкой флага остановки каждые 60 секунд
                    while sleep_seconds > 0 and self.is_running:
                        wait_time = min(60, sleep_seconds)
                        await asyncio.sleep(wait_time)
                        sleep_seconds -= wait_time
                
                # Выполняем синхронизацию, если не остановлены
                if self.is_running:
                    await self._perform_sync_with_retry()
                
        except asyncio.CancelledError:
            app_logger.info("Цикл планировщика отменен")
        except Exception as e:
            app_logger.error(f"Критическая ошибка в планировщике: {e}")
    
    def _calculate_next_sync_time(self) -> datetime:
        """Вычисляет время следующей синхронизации"""
        now = datetime.now()
        
        # Если кэш свежий, синхронизация через интервал от последней
        if self.cache_manager.is_cache_fresh():
            try:
                # Получаем время последней синхронизации
                import sqlite3
                with sqlite3.connect(self.cache_manager.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT value FROM cache_metadata WHERE key = 'last_full_sync'"
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        last_sync = datetime.fromisoformat(result[0])
                        return last_sync + timedelta(hours=self.sync_interval_hours)
            except Exception as e:
                app_logger.error(f"Ошибка получения времени последней синхронизации: {e}")
        
        # По умолчанию - синхронизация сейчас
        return now
    
    async def _perform_sync_with_retry(self):
        """Выполняет синхронизацию с повторными попытками при ошибках"""
        for attempt in range(self.max_retries):
            try:
                app_logger.info(f"Синхронизация товаров (попытка {attempt + 1}/{self.max_retries})")
                
                result = await self.cache_manager.sync_from_moysklad()
                self.last_sync_result = {
                    **result,
                    "timestamp": datetime.now().isoformat(),
                    "attempt": attempt + 1
                }
                
                if result.get("status") == "success":
                    app_logger.info(f"Синхронизация успешна: {result}")
                    return
                elif result.get("status") == "skipped":
                    app_logger.info("Синхронизация пропущена (не нужна)")
                    return
                else:
                    app_logger.warning(f"Синхронизация не удалась: {result}")
                
            except Exception as e:
                app_logger.error(f"Ошибка синхронизации (попытка {attempt + 1}): {e}")
                self.last_sync_result = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "attempt": attempt + 1
                }
            
            # Ждем перед повтором (кроме последней попытки)
            if attempt < self.max_retries - 1:
                app_logger.info(f"Ждем {self.retry_interval_minutes} минут перед повтором...")
                await asyncio.sleep(self.retry_interval_minutes * 60)
        
        app_logger.error(f"Все {self.max_retries} попытки синхронизации неуспешны")
    
    async def force_sync(self) -> dict:
        """
        Принудительная синхронизация (вне расписания)
        
        Returns:
            Результат синхронизации
        """
        app_logger.info("Принудительная синхронизация товаров")
        
        try:
            result = await self.cache_manager.sync_from_moysklad(force=True)
            self.last_sync_result = {
                **result,
                "timestamp": datetime.now().isoformat(),
                "forced": True
            }
            return result
            
        except Exception as e:
            app_logger.error(f"Ошибка принудительной синхронизации: {e}")
            result = {
                "status": "error", 
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "forced": True
            }
            self.last_sync_result = result
            return result
    
    def get_status(self) -> dict:
        """
        Получает текущий статус планировщика
        
        Returns:
            Информация о состоянии планировщика
        """
        cache_stats = self.cache_manager.get_cache_stats()
        
        next_sync = None
        if self.is_running:
            next_sync_time = self._calculate_next_sync_time()
            next_sync = next_sync_time.isoformat()
        
        return {
            "scheduler_running": self.is_running,
            "sync_interval_hours": self.sync_interval_hours,
            "next_sync_time": next_sync,
            "last_sync_result": self.last_sync_result,
            "cache_stats": cache_stats
        }
    
    async def get_cache_products(self, **search_params) -> List[dict]:
        """
        Получает товары из кэша с параметрами поиска
        
        Args:
            **search_params: Параметры поиска для передачи в cache_manager
            
        Returns:
            Список товаров из локального кэша
        """
        return await self.cache_manager.search_cached_products(**search_params)