class TaskManager:

    def __init__(self):
        self.active_task = None
        self.history = []
        self.completed_steps = []
        self.is_complete = False

    def start_task(self, user_input):
        self.active_task = user_input
        self.history = []
        self.completed_steps = []
        self.is_complete = False

    def add_step(self, step, result):
        if step not in self.completed_steps:
            self.history.append({
                "step": step,
                "result": result
            })
            self.completed_steps.append(step)

    def get_context(self):
        return {
            "task": self.active_task,
            "history": self.history,
            "completed": self.completed_steps,
            "complete": self.is_complete
        }

    def mark_complete(self):
        self.is_complete = True

    def has_active_task(self):
        return self.active_task is not None

    def clear(self):
        self.active_task = None
        self.history = []
        self.completed_steps = []
        self.is_complete = False


task_manager = TaskManager()