# SoundSense

## Motivation

I play D&D, and one of the strangely intriguing parts has been to find music to fit the mood.  There are many different music organization systems out there, but most of them focus on methods that things like Genre, Author, Instrumental type, things like that.  I didn't need that kind of organization: I needed to organize based on what made good playlists for specific types of environments or encounters.  There were a few applications that offered music that would work in these situations, but it was all generic music.  I wanted to be able to use music that I had a connection to, like music from certain video games, movies, TV, and other media.

I immediately struggled with finding an app that would work for me.  Youtube would work in theory, but it had so many ads, which is super immersion breaking.  I ended up using the built in Roll20 audio player, which is fine, but makes managing your music an absolute chore.  Playlists could be added multiple times, with different songs in each added playlist, and the player could get desynced easily.

I finished my Curse of Strahd campaign using the Roll20 audio player, but was searching for other options.  Discord bots in general seemed like a bad choice.  I didn't want a bot that required me to queue up a bunch of songs.  I also knew that many music bots had copywrite issues, so they seemed unreliable long term.

Enter Kenku FM.  Made by the people over at Owlbear, Kenku lets me play audio to others in the Discord call, using either local songs in a playlist, or an internal browser to play music.  At first I thought this would be perfect for me: all I had to do was figure out how Kenku stored playlists of songs, and I could just write a custom playlist to that storage, and Kenku would pick it up!  I ran into more issues with this, mostly being that I am unfamiliar with how Electron and React applications store information between sessions... 

I have used Kenku for a while, but I have begun to chafe under the tyranny of simple, static playlists.  I have had an idea to create dynamic playlists from user generated tags for a while.  Since Kenku could play music from an internal browser to Discord, I figured that I could try and create a web app that would let me tag songs and create dynamic playlists.  This is how SoundShare was born.  If you have a better name, please give me a suggestion.

## Web Apps for Dummies

### I'm a coward

I don't do front-end.  This is not a value judgment, it's just not where my career has taken me.  I understand how HTML and CSS work in theory, and have written some JavaScript, but I have never designed a theme for a website from scratch.  I decided that, instead of writing everything from scratch, I needed to get to MVP relatively quickly, instead of struggling with the things I wasn't familiar with.  I decided to lean on Claude Sonnet 4, which I had heard good things about.

The concept _felt_ simple: Allow the user to import songs into the system, listen to the song/a short preview segment, add tags to the song, and create dynamic playlists that plays songs that match the defined tags.  Like everything, the devil was in the details.

### AI and You

I feel like my experience having an AI write all of the code for my project would be a good blog post.  Overall, it was obviously very helpful.  The initial "prompt" generated multiple full pages of working code.  After that, I did struggle to get the AI to generate what I wanted.  It did not do a good job of preemptively refactoring code, which made future work difficult as Claude had to make changes in many different files at once.  It also did not "share" my vision, so I found that implementation details were often poorly done and did not mesh well with future work.  I can't blame the AI for not reading my mind, but it's interesting how AI is said to replace developers.  If I did not carefully steer the AI in the right direction, it would have made the project more and more unmaintainable (by me).  It did not seem to understand what makes good, maintainable code at all, instead it created as many functions, tables, columns, and routes as it felt it needed.  It also did not like standardizing anything, and I had to ask it to create reusable components multiple times.  It did, however, suggest some of these options when I asked it to find issues in the code base, so it certainly has the capacity to look for issues: you just have to prompt it to do so.

## Epilogue

You will notice that this README is full of poorly written sentences and half thought out paragraphs.  That is because I want to leave this monument scratched on top of the AI code heap that resides here.  You know I am human, because an AI would not write garbage like this.  I leave you with this warning.

AI creates and creates, but it doesn't know how to ask "why".  It doesn't push back, it doesn't say something is unreasonable, it doesn't understand how what it creates could be better, if we put some Sprint items in for fixing code smells.  It is the code smell.  This code is bloated and unmaintainable by the maintainer.  Does it work? Yes.  Will it work in the future? Probably not.  I will update as needed to use this to play dynamic playlists of manually tagged songs over Kenku, but at some point this will be a relic, a reminder of all of the electricity used up to type out letters, that will have no purpose.

Maybe some day I will learn front-end and do this again, the right way.

Or maybe I'll just make this some complicated Click CLI.

## PS

Check the AI_README to see what the AI thinks of this project.
