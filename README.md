# ATM Seminar Lektor Source Code

This is the Lektor source code for the website https://www.atmseminar.org.  This project is written in the [Lektor Content Management System - Static Site Generator](https://www.getlektor.com).

## Content

The content of the site is located in [content](./content/) subdirectory.  Per the Lektor documentation, each `contents.lr` file holds an UTF-8 text file representing the content of that page written in [Markdown](https://commonmark.org/help/) format.  Papers are kept in a [Google Drive folder](https://drive.google.com/drive/folders/1aD26KOoAl1_jifbvZN8mU8ZD8jA1vj4T?usp=sharing).  

Each individual yearly conference page has a subdirectory `papers` which holds a comma separated values file called papers.csv.  This attachment contains the meta-info of the individual papers (title, author, abstract) as well as the drive folder path within that Google drive repository.  A lektor plugin generates a listing page with the presentations and papers resolved to their Google Drive identifier.

Individual templates are located in the [templates folder](./templates/)

## Customized template functionality.

A JSON file in the [databags folder](./databags/) holds the mapping between the drive path and the identifiers.  This JSON file is created by a [separate utility made for this project](https://github.com/atmseminar-org/pydrivelist).  If you would like to generate this file for development purposes, you'll need to be added as a user.  

A [plugin](./packages/conference-template-functions) was created to do the mapping between the Google Drive.

This can be installed from the root with the command `lektor plugins reinstall`.

## Installation

[Install the lektor command line application](https://www.getlektor.com/docs/installation/).

Clone this repository, and at the project root use the command `lektor plugins reinstall`.

You can now use `lektor server` to host a [local version of the site](http://localhost:5000/) defaulting to localhost at port 5000.

## Updates

Site updates can come either as pull requests to this repository, or if you have push permissions to the [Github Pages repository](https://github.com/atmseminar-org/atmseminar-org.github.io) then you can execute the lektor command

`lektor deploy ghpages --key-file [YOUR_PUBLIC_SSH_KEY_FILE]`

Where `[YOUR_PUBLIC_SSH_KEY_FILE]` is the ssh key file associated with your github account.
