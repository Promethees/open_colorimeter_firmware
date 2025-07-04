import board
import displayio
import constants

class SplashScreen:

    def __init__(self):
        filename = f'{constants.SPLASHSCREEN_BMP}'
        self.bitmap = displayio.OnDiskBitmap(filename)
        self.tile_grid = displayio.TileGrid(
                self.bitmap, 
                pixel_shader=self.bitmap.pixel_shader, 
                )
        self.group = displayio.Group()
        self.group.append(self.tile_grid)

    def show(self):
        board.DISPLAY.root_group = self.group
        
    def clear(self):
        """Free all resources used by the splash screen"""
        # Remove the group from display
        board.DISPLAY.root_group = None
        
        # Remove tile grid from group
        if self.tile_grid in self.group:
            self.group.remove(self.tile_grid)
            
        # Deallocate resources
        self.group = None
        self.tile_grid = None
        self.bitmap = None