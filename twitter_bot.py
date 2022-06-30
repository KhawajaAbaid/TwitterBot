"""A sort of general purpose twitter bot class that handles all the basic
functions of a twitter bot.
It is meant to be subclassed by an other script that implements the actual
bot specific functions."""

import datetime
import tweepy
import logging
import nltk
import configparser
import json
import string


class TwitterBot:
    def __init__(self, 
                    bot_id:str, 
                    config_file_path:str):
        """Initializes the bot.
        Args:
            bot_id: The id of the bot.
            config_file_path: The path to the config file that contains your twitter credentials.
        """
        self.date = datetime.datetime.today().strftime('%d_%m_%Y')
        logging.basicConfig(filename=f"logs/twitter_bot_{self.date}.log", level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            filemode='a+')
        logging.info("Twitter Bot Activated.")

        # the twitter id of your bot
        self.bot_id = bot_id

        # Let's define our stop words here
        # If you're not familiar with stop words, they are the most commonly ccuring
        # words in texts, like the, a, and, of, etc.
        self.stop_words = nltk.corpus.stopwords.words('english')
        self.stop_words.extend(list(string.punctuation))

        # Let's get out twitter API up and running
        # Note that I'm importing my twitter API credentials from a config file
        # Obviously the conifg file isn't in the repo, so to make this script work
        # you'll need to provide your own credentials.

        # Note: twitter-app-data section contains the credentials of project/app in your twitter developer account
        # while the twitter-bot-data section contains credentials or access token and secret of the bot.
        logging.info("Initiatign Authentication Process.")
        config = configparser.ConfigParser()
        config.read(config_file_path)
        bearer_token = config["twitter-app-data"]["bearer"]
        consumer_key = config['twitter-app-data']['consumer_key']
        consumer_secret = config['twitter-app-data']['consumer_secret']
        access_token = config['twitter-bot-data']['access_token']
        access_secret = config['twitter-bot-data']['access_token_secret']

        self.api_v2 = tweepy.Client(bearer_token, consumer_key, consumer_secret,
                                    access_token, access_secret)

        # We need API v1 to upload media since twitter's api v2 doesn't
        # support uploading media yet.
        auth_v1 = tweepy.OAuthHandler(consumer_key, consumer_secret,
                                      access_token, access_secret)
        self.api_v1 = tweepy.API(auth=auth_v1)
        logging.info("Authentication Completed.")

    def get_last_seen_tweet_id(self):
        """Gets the last seen tweet id."""

        logging.info("Retrieing last seen tweet ID")
        with open("validation_data/last_seen_tweet_id.txt", "r") as f:
            last_seen_id = int(f.read().strip())
            logging.info(f"last seen id: {last_seen_id}")
            return last_seen_id

    def store_last_seen_tweet_id(self, last_seen_tweet_id: int):
        """Stores the last seen tweet id in a file.
        Args:
            last_seen_tweet_id: ID of the last user processed
        Returns:
            Nothing
        """
        logging.info("Storing last seen tweet ID")
        last_seen_tweet_id = last_seen_tweet_id
        with open("validation_data/last_seen_tweet_id.txt", "w") as f:
            f.write(str(last_seen_tweet_id))
        return

    def validate_user(self, user_id: str):
        """Validates a user id.
        Args:
            user_id: The id of the user to validate.
        Returns:
            True if the user is valid, False otherwise.
            By valid we mean user has not made more than 5 requests in a day.
            If they have, they will be put limit reached json file.
        """
        logging.info("Validating user")
        with open("validation_data/users_data.json", "r") as f:
            users_data = json.loads(f.read())
        if str(user_id) in users_data.keys():
            user_requests = users_data[str(user_id)]['requests']
        # if users record doesnt exist yet then the user has made no requests
        # hence they are valid. As for creating record we do so with update validation data method
        else:
            return True
        if int(user_requests) >= 5:
            return False
        else:
            return True

    def update_validation_data(self, user_id: str):
        """Updates the validation data.
        Args:
            user_id: The id of the user to update.
        """
        logging.info("Updating validation data")
        with open("validation_data/users_data.json", "r") as f:
            users_data = json.loads(f.read())
        if str(user_id) in users_data.keys():
            users_data[str(user_id)]['requests'] += 1
        else:
            new_user_data = {f"{user_id}": {'requests': 1}}
            users_data = {**users_data, **new_user_data}
        with open("validation_data/users_data.json", "w") as f:
            f.write(json.dumps(users_data))
        return

    # this func above was written by Github Copilot. Good bot!

    def get_mentions(self):
        """Gets the mentions of the bot.
        Returns:
            A list of mentions, along with meta data about users.
        """
        logging.info("Retrieving mentions")
        last_seen_tweet_id = self.get_last_seen_tweet_id()
        # the twitter id of the TweetsCloudBot
        bot_id = self.bot_id
        try:
            mentions = self.api_v2.get_users_mentions(bot_id, since_id=last_seen_tweet_id, expansions="author_id",
                                                      user_fields=["username"])
            mentions_data = mentions.data
            users_metadata = mentions.includes["users"]
            return mentions_data, users_metadata
        except:
            logging.error("Couldn't retrieve mentions")
            return [], []

    def fetch_tweets(self, user_id: str):
        """Fetches tweets from a given username.
        Args:
            user_id: The id of of the user to fetch tweets from.
        Returns:
            A list of tweets.
        """
        logging.info("Fetching tweets")
        # user = self.api_v2.get_user(username)
        tweets = self.api_v2.get_users_tweets(id=user_id, max_results=100)
        tweets = tweets.data
        return tweets

    def preprocess_and_tokenize_tweets(self, tweets: list):
        """Preprocesses and tokenizes tweets.
        Args:
            tweets: A list of tweets where each tweet is wrapped in
            object of type pytwitter.models.tweet.Tweet.
        Returns:
            A list of words or tokens.
        """
        all_words = []
        for tweet in tweets:
            tweet_text = tweet.text
            words = nltk.tokenize.casual.casual_tokenize(tweet_text,
                                                         preserve_case=False,
                                                         reduce_len=True,
                                                         strip_handles=True)
            words = [word for word in words if word not in self.stop_words]
            all_words.extend(words)
        return all_words

    def reply_with_limit_reached(self, tweet_id: str, user_screen_name: str):
        """Replies to a tweet.
        Args:
            tweet_id: The id of the tweet to reply to.
            user_screen_name: The screen name of the user.

        """
        logging.info("Replying with limit reached message")
        reply_text = f"Hi {user_screen_name}, Sorry, but you've reached your daily limit of " \
                     "5 requests per day. " \
                     "Please try again tomorrow."
        self.api_v2.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        return

    def validate_input(self, required_input=None, tweet_text: str = None):
        """Validates the input
        Args:
            required_input: The input that the bot requires to run. Can be a string or list of strings.
            tweet_text: The text of the tweet.
        Returns:
            True or False based on whether the mention/tweet includes required input Make Tweets Cloud.
            """
        tweet_text = str(tweet_text).lower()
        if type(required_input) == list:
            for r_input in required_input:
                if r_input in required_input:
                    return True
            return False

        elif type(required_input) == str:
            if required_input in tweet_text:
                return True
            else:
                return False

    def get_params_from_tweet(self, tweet_text: str = None,
                              params_dict: dict = None):
        """Extracts parameters from a tweet.
        Args:
            tweet_text: The text of the tweet.
            params_dict: A dict of params that the bot expects to see. Should include each parameter as key
            and a list of its allowed values as value. For example, {'color': ['black', 'white'], 'border':['yes', 'no']
        Returns:
            A dictionary of parameters.
        """
        logging.info("Extracting parameters from tweet")
        params = {}
        tweet_text = tweet_text.lower()

        for param in params_dict.keys():
            for value in params_dict[param]:
                if value in tweet_text:
                    params[param] = value
                    break
        return params

        # params["mode"] = "default"
        # mode = "default"
        # if "sketch" in tweet_text:
        #     mode = "sketch"
        #     params["mode"] = mode

        # if "black" in tweet_text:
        #     params["background_color"] = "black"
        # elif "white" in tweet_text:
        #     params["background_color"] = "white"
        # else:
        #     if mode == "default":
        #         params["background_color"] = "black"
        #     elif mode == "sketch":
        #         params["background_color"] = "white"

        # if "no border" in tweet_text:
        #     params["border"] = False
        # else:
        #     params["border"] = True
        # return params

    def bot_handler(self):
        """Handles the bot.
        To be overwritten by the child class as bots serve different purposes
        and thus must be handled in tandem.
        """
        pass
