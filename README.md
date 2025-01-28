# Constructo

Constructo is an AI-powered pentesting and security agent designed to assist with executing commands, analyzing logs, and making decisions based on the analysis. It is built to work with Linux/Kali commands and provides a detailed log of all actions.

## Features

- Execute Linux/Kali commands
- Analyze logs and outputs
- Make decisions based on analyses
- Request confirmation for critical actions
- Rate limiting and retry logic for API calls

## Prerequisites

- A Linux-based system.
- Python 3.7+
- An Google Generative AI API key.
  - You can request access to the API [here](https://aistudio.google.com).

## Configuration

Constructo uses a configuration file (`config.yaml`) to manage settings. Below is an example configuration:

```yaml
api_key: "YOUR_API_KEY_HERE"
model:
  name: "gemini-2.0-flash-exp"
  max_output_tokens: 4096
  temperature: 0.7
  top_p: 0.9
  top_k: 40

security:
  require_confirmation: false  # false to disable all confirmations
  risk_threshold: "medium"   # "none", "low", "medium", "high" - only ask for risks above this level

api:
  rate_limit:
    requests_per_minute: 10  # Maximum requests per minute
    delay_between_requests: 5  # Delay in seconds between requests
  retry:
    max_attempts: 3  # Maximum number of retry attempts
    delay_between_retries: 10  # Delay in seconds between retries
```

### Configuration Parameters

- **api_key**: Your API key for the generative AI service.
- **model**: Configuration for the AI model.
  - **name**: Name of the model.
  - **max_output_tokens**: Maximum number of tokens in the output.
  - **temperature**: Sampling temperature.
  - **top_p**: Top-p sampling parameter.
  - **top_k**: Top-k sampling parameter.
- **security**: Security settings.
  - **require_confirmation**: Whether to require confirmation for actions.
  - **risk_threshold**: Minimum risk level to require confirmation.
- **api**: API settings.
  - **rate_limit**: Rate limiting settings.
    - **requests_per_minute**: Maximum number of requests per minute.
    - **delay_between_requests**: Delay in seconds between requests.
  - **retry**: Retry settings.
    - **max_attempts**: Maximum number of retry attempts.
    - **delay_between_retries**: Delay in seconds between retries.

## Running Constructo

1. Clone the repository:
   ```sh
   git clone https://github.com/Rafael-BD/Constructo.git
   cd Constructo
   ```

2. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Configure your settings in `config.yaml`.

4. Run the main script:
   ```sh
   python src/main.py
   ```

## Development Progress

### Completed Features
- [x] Basic chat functionality
- [x] Execution of common Linux/Kali commands
- [x] Log analysis and decision making
- [x] Request confirmation for critical actions
- [x] Rate limiting and retry logic for API calls

### Upcoming Features
- [ ] Support for interactive tools (e.g., msfconsole, sqlmap)
- [ ] Persistent memory and learning system
- [ ] Deep reasoning module
- [ ] Support for additional AI APIs

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
