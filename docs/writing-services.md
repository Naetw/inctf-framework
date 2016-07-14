# Writing services

To include a new service with this infrastructure, the following are required:

1. JSON configuration of the service with the following information:
    - name: string. Name of service.
    - authors: [List of strings]. Name(s) of author(s)
    - flag_id_description: string. Describe what data in service is flag ID.
    - service_description: string. Description of the service.
    - port: int. The port number on which the service listens.
    - user: string. The user with whose privileges the service runs inside the
      container.
    - workdir: string. The working directory for the service inside the container.
    - command: string. The command to run when the service container is started.
    - getflag: string. Relative path to the getflag script.
    - setflag: string. Relative path to the setflag script.
    - is_working: int. This is currently ignored and included for compatibility with
      iCTF framework.
2. Debian packaged version of the service.
3. A setflag and getflag script to respectively store and retrieve flags from the
   service.

The JSON configuration, setflag and getflag scripts should be stored in a folder with
name of the service and the Debian package should be present one level above the JSON
configuration and script files. There are few sample services present in the
services/ folder which would help getting started with writing services.

*IMPORTANT*: The service name should not contain underscores ('_') since that affects
the processing of callbacks from Docker distribution. We recommend using hyphen('-')
instead.
