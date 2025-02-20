import os
import logging
from pathlib import Path
import requests
from tqdm import tqdm
import schedule
import time
from ..utils.file_utils import download_file

class ModelUpdater:
    def __init__(self, config, update_interval_seconds=60):
        self.config = config
        self.models_directory = Path(self.config['base_dir'])
        self.model_config_url = self.config['model_config_url']
        self.vae_config_url = self.config['vae_config_url']
        self.update_interval_seconds = update_interval_seconds
        self.session = requests.Session()  # Use a session for connection pooling
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Configure logging

    def fetch_remote_model_list(self):
        """Fetch the combined list of models and VAEs from the configured URLs."""
        combined_models = []
        urls = [self.model_config_url, self.vae_config_url]

        for url in urls:
            try:
                response = self.session.get(url)
                response.raise_for_status()  # Raises HTTPError for bad responses
                models = response.json()
                if isinstance(models, list):  # Ensure the response is a list
                    combined_models.extend(models)
                else:
                    logging.warning(f"Unexpected format received from {url}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch data from {url}: {e}")
                return None

        return combined_models

    def is_update_required(self, remote_model_list):
        """Check if the remote model list contains models that are not present locally."""
        # Get the list of local files without the '.safetensors' extension
        local_files = os.listdir(self.models_directory)
        local_model_names = {file_name.rsplit('.', 1)[0] for file_name in local_files if file_name.endswith('.safetensors')}

        # Get the set of model names from the remote model list
        remote_model_names = {model_info['name'] for model_info in remote_model_list}

        # Determine if there are any models that are in the remote list but not locally
        missing_models = remote_model_names - local_model_names
        if missing_models:
            print(f"Missing models that require download: {missing_models}")
            return True
  
        return False  # No update required if all models are present

    def download_single_model(self, model_info):
            model_name = model_info['name']
            model_url = model_info['file_url']
            model_size_mb = model_info['size_mb']
            file_name = f"{model_name}.safetensors"

            # The path where the model will be saved
            model_path = os.path.join(self.models_directory, file_name)
            
            # Only download if the model file doesn't already exist
            if not os.path.exists(model_path):
                print(f"Downloading new model: {model_name}")
                download_file(self.models_directory, model_url, file_name, model_size_mb * 1024 * 1024)

    def update_config_single_model(self, model_info):
        model_name = model_info['name']
            # Check if it's a model or a VAE based on some criteria, for example, the presence of a specific key
        if 'vae' in model_info:
            # It's a VAE, update vae_configs
            if model_name not in self.config['vae_configs']:
                self.config['vae_configs'][model_name] = model_info
        else:
            # It's a regular model, update model_configs
            if model_name not in self.config['model_configs']:
                self.config['model_configs'][model_name] = model_info

    def download_new_models(self, remote_model_list):
        """Download new models from the remote list that are not present in the local directory."""
        for model_info in remote_model_list:
            self.download_single_model(model_info)
    
    def update_configs(self, remote_model_list):
        """Update local configuration with new models from the remote list."""
      # Iterate through the remote model list and update config.model_configs
        for model_info in remote_model_list:
            self.update_config_single_model(model_info)

    def update_models(self):
        """Update models by checking for new models and downloading them if necessary."""
        remote_model_list = self.fetch_remote_model_list()
        if not remote_model_list:
            print("Could not fetch remote model list. Skipping update.")
            return

        if self.is_update_required(remote_model_list):
            self.download_new_models(remote_model_list)
            self.update_configs(remote_model_list)
            print("Model updates completed.")
        else:
            print("No model updates required.")

    def start_scheduled_updates(self):
        """Start periodic model updates based on the specified interval."""
        schedule.every(self.update_interval_seconds).seconds.do(self.update_models)
        print(f"Scheduled model updates every {self.update_interval_seconds} seconds.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    def update_single_model(self, model_id):
        """Update a single model by name."""
        remote_model_list = self.fetch_remote_model_list()
        if not remote_model_list:
            print("Could not fetch remote model list. Skipping update.")
            return
        
        model_info = next((model for model in remote_model_list if model['name'] == model_id), None)

        if model_info:
            self.download_single_model(model_info)
            self.update_config_single_model(model_info)
            print(f"Model update completed for {model_info['name']}.")
        else:
            print(f"Model {model_id} not found in the remote list.")