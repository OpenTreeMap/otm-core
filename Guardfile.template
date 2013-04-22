#
# This can be used to watch your directory for changes and
# automatically update django on a remote vm
#
# To use it you'll first have to install guard. Guard is a
# ruby based program so you'll have to install ruby first.
#
# To install guard:
# > gem install guard rb-inotify rb-fsevent rb-fchagne
#
# Then run it with:
# guard in your root directory

guard :shell do
  watch(%r{^.*/static/.*$}) { `fab vagrant static` }
  watch(%r{.*}) { `fab vagrant restart_app` }
end
