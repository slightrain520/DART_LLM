import re

def validate_user_input(user_input):
    """
    Validates user input for sensitive words or inappropriate length.

    Args:
        user_input (str): The input provided by the user.

    Returns:
        bool: True if the input is valid, False if it contains sensitive content or exceeds length limits.
    """
    # Check for sensitive words (for demonstration, you can replace with actual lists)
    sensitive_words = ["badword1", "badword2"]  # Example list of sensitive words
    for word in sensitive_words:
        if word in user_input:
            print(f"Input contains sensitive word: {word}")
            return False
    
    # Check length (example length limit)
    if len(user_input) > 500:
        print("Input exceeds maximum length.")
        return False

    return True

def validate_prompt(final_prompt):
    """
    Validates the security of the final prompt to ensure no harmful content.

    Args:
        final_prompt (str): The final prompt constructed from user input and context.

    Returns:
        bool: True if the prompt is safe, False if harmful content is detected.
    """
    # Check for harmful patterns (e.g., SQL injections, harmful scripts, etc.)
    harmful_patterns = [r"<script>", r"SELECT * FROM", r"DROP TABLE"]  # Example patterns
    for pattern in harmful_patterns:
        if re.search(pattern, final_prompt):
            print(f"Harmful pattern detected: {pattern}")
            return False

    return True
