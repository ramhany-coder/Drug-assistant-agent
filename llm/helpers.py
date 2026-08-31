class Helpers:
    routers_list = ["anthropic", "gemini", "gpt", "groq", "ollama"]

    @staticmethod
    def validate_router(router: str) -> str:
        if not isinstance(router, str):
            raise ValueError(f"Router must be a string, got {type(router).__name__}.")

        router = router.strip().lower()

        if router not in Helpers.routers_list:
            raise ValueError(
                f"Invalid router '{router}'. Must be one of: {Helpers.routers_list}"
            )

        return router
