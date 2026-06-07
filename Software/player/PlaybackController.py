

class PlaybackController:
    def __init__(self):
        self.state = "stopped"
        self.current_file = None

        
        

    def play(self, file):
        self.state = "playing"
        self.current_file = file

    def stop(self):
        self.state = "stopped"
        self.current_file = None

    def pause(self):
        self.state = "paused"
        self.current_file = None