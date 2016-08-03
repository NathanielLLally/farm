#!/usr/bin/perl
#
package Farm;

use DigitalOcean;
use Try::Tiny;
use Data::Dumper;
use Moose;
use DateTime;

has 'oauth_token' => (
  is => 'ro',
  isa => 'Str', 
  default => sub {
    if (open(DOT, "<$ENV{HOME}/.digital_ocean")) {
      while(<DOT>) {
        chomp;
        if ($_ =~ /api_key\s+=\s+['"]?(([0-9]|[a-z])+)['"]?/) {
          print "$1\n";
          return $1;
        }
      }
    } else {
      open(DOT, ">$ENV{HOME}/.digital_ocean") || die 'cannot open dot file for writing';
      print DOT "api_key = 'insert your api key'\n";
      close DOT;
      chmod 0600, "$ENV{HOME}/.digital_ocean";
      die 'please insert your api key into ~/.digital_ocean';
    }
  },
);

has 'do' => (is => 'rw', isa => 'DigitalOcean',
  lazy => 1,
  default => sub {
    my $s = shift;
    my $do = DigitalOcean->new(oauth_token => $s->oauth_token, time_between_requests => 1);
    $do->die_pretty(undef);
    $do;
  }
);

sub printUser {
  my $s = shift;
  my $account = $s->do->get_user_information;
  print "Droplet limit: " . $account->droplet_limit . "\n";
  print "Email: " . $account->email . "\n";
  print "uuid: " . $account->uuid . "\n";
  print "Email Verified: " . $account->email_verified . "\n";
}

sub remainingDroplets {
  my $s = shift;
  my $account = $s->do->get_user_information;
  my $max = $account->droplet_limit;
  return $max - $s->total_droplets;
}

has '_droplets' => (
  is => 'rw', 
  isa => 'HashRef', 
  traits => ['Hash'],
  lazy => 1, 
  handles => {
    droplet_names => 'keys',
    droplets => 'values',
    total_droplets => 'count',
    name_for_droplet => 'get',
  },
  builder => '_get_droplets',
);

sub _get_droplets {
  my $s = shift;
  my $droplets = $s->do->droplets;
  my $obj;
  my $hashRef;
  while($obj = $droplets->next) {
    $hashRef->{$obj->name} = $obj;
  }
  $hashRef;
}

sub refresh_droplets
{
  my $s = shift;
  $s->_droplets($s->_get_droplets);
}

has '_images' => (
  is => 'rw', 
  traits => ['Hash'],
  isa => 'HashRef',
  lazy => 1, 
  handles => {
    user_image_names => 'keys',
    user_images => 'values',
    total_user_images => 'count',
    name_for_user_image => 'get',
  },
  default => sub {
    my $s = shift;
    my $images = $s->do->user_images;
    my $obj;
    my $hashRef;
    while($obj = $images->next) {
      $hashRef->{$obj->name} = $obj;
    }
    $hashRef;
  }
);


sub printDOerror {
  my $do_error = shift;
       print "id: " . $do_error->id . "\n";
       print "message: " . $do_error->message . "\n";
       print "status_code: " . $do_error->status_code . "\n";
       print "status_line: " . $do_error->status_line . "\n";
}

sub deleteSheep {
  my $s = shift;
  my $n = shift;
  foreach my $obj ($s->droplets) {
   if ($obj->name =~ /^sheep(\d+)/) {
     my $i = $1;
     if (defined $n) {
       if ($i > $n) {
         print "removing ".$obj->name."\n";
         try {
           $obj->delete;
         } catch {
           printDOerror($_);
         };
       }
     } else {
       print "removing ".$obj->name."\n";
       try {
         $obj->delete;
       } catch {
         printDOerror($_);
       };
     }
   }
 }
 $s->deleteDNSrecords;
 $s->waitOnActions;
}

sub printHosts
{
  my $s = shift;
  foreach my $obj ($s->droplets) {
   my $net = $obj->networks->v4;
   foreach my $if (@{$net}) {
     printf("%s\t%s\n", $if->ip_address, $obj->name);
   }

 }
}

sub printDropletInfo
{
  my $s = shift;
  foreach my $obj ($s->droplets) {
    my $ip = @{$obj->networks->v4}[0]->ip_address;
    printf("%s(%i) %s %s %s (%imb ram %i vcpus %igb disk)\n",
      $obj->name, $obj->id, $ip, $obj->region->slug, $obj->size->slug,
      $obj->memory, $obj->vcpus, $obj->disk);

#  my $net = $obj->networks->v4;
#   foreach my $if (@{$net}) {
#     printf("\t%s\n", $if->ip_address);
#   }

 }
}

sub printSizes
{
  my $s = shift;
      my $sizes_collection = $s->do->sizes;
    my $obj;

    while($obj = $sizes_collection->next) { 
        print $obj->slug . "\n";
    }
}

sub printRegions
{
  my $s = shift;
      my $regions_collection = $s->do->regions;
    my $obj;

    while($obj = $regions_collection->next) { 
        print $obj->slug . " - " . $obj->name . "\n";
    }
}

sub printUserImages
{
  my $s = shift;
  print "User Images:\n";
  foreach my $obj ($s->user_images) {
   printf("%s(%i)\n", $obj->name, $obj->id,);
  }
}

sub getI
{
  my $s = shift;
  my $max = 0;
  foreach my $obj ($s->droplets) {
    if ($obj->name =~ /^sheep(\d+)/) {
      my $n = $1;
      if ($n > $max) {
        $max = $n;
      }
    }
  }
  return $max + 1;
}

sub makeSheep
{
  my $s = shift;
  my $image_name = shift || 'dolly-seed1';
  my $n = shift || 1;
  my $image = $s->name_for_user_image($image_name);
  if (not defined $image) {
    die "image $image_name does not exist";
  }

  my $i = $s->getI;
  $n += ($i - 1);
  print "creating $n droplets...\n";
  foreach my $j ($i..$n) {
    try {
      $s->do->create_droplet(
        name => "sheep$j",
        region => 'nyc1',
        size => '8gb',
        image => $image->id,
      );
    } catch {
       printDOerror($_);
    };
  }

   $s->waitOnActions;

   $s->makeDNSrecords;
   $s->cleanSSHKeyCache;
}

sub waitOnActions
{
  my $s = shift;
  my $region = 'nyc1';
  my $type = shift;

    my $complete;
    do {
      $complete = 0;
      my $actions_collection = $s->do->actions;
      my $obj;
      while($obj = $actions_collection->next) { 
        if (not defined $obj->completed_at 
            and $obj->status ne 'errored'
#            and $obj->region_slug eq 'nyc1'
            ) {
          $complete++;
          printf("action %i %s %s %s %s %s\n", $obj->id, $obj->status, $obj->type, 
          $obj->started_at, (defined $obj->region_slug)?$obj->region_slug:'N/A', DateTime->now->datetime());
        }
      }
      if ($complete > 0) {
        sleep 2;
      }
    } while ($complete > 0);
}

sub deleteDNSrecords
{
  my $s = shift;
  my $domain = $s->do->domain('airitechsecurity.com');
  my $records_collection = $domain->records;
  my $obj;

  while($obj = $records_collection->next) { 
    if ($obj->name =~ /^sheep/) {
      $obj->delete;
    }
  }
}

sub makeDNSrecords
{
  my $s = shift;

  my $domain = $s->do->domain('airitechsecurity.com');
  $s->refresh_droplets;
  foreach my $obj ($s->droplets) {
    if ($obj->name =~ /^sheep/) {
      my $ip = @{$obj->networks->v4}[0]->ip_address;
      printf("%s.airitechsecurity.com -> %s\n",$obj->name,$ip);
      $domain->create_record(
          type => 'A',
          name => $obj->name,
          data => $ip,
          );
    }
  }
}

sub cleanSSHKeyCache
{
  my $s = shift;
  $s->refresh_droplets;
  foreach my $obj ($s->droplets) {
    if ($obj->name =~ /^sheep/) {
      open(CMD,"ssh-keygen -R ".$obj->name."|") || die 'cannot open cmd ssh-keygen';
      while(<CMD>) {
        print $_;
      }
      close(CMD);
    }
  }
}

no Moose;
__PACKAGE__->meta->make_immutable;

package main;

my $cmd = shift || 'info';

my $farm = Farm->new();

print "remaining droplets: ".$farm->remainingDroplets."\n";

if ($cmd eq 'create') {
  my $image = shift || 'sheep1-slave';
  my $n = shift || 1;
  $farm->makeSheep($image, $n);
} elsif ($cmd eq 'delete') {
  my $n = shift;
  $farm->deleteSheep($n);
} elsif ($cmd eq 'images') {
  $farm->printUserImages;
} elsif ($cmd eq 'info') {
  $farm->printDropletInfo;
} elsif ($cmd eq 'hosts') {
  $farm->printHosts;
} elsif ($cmd eq 'dns') {
  $farm->deleteDNSrecords;
  $farm->waitOnActions;
  $farm->makeDNSrecords;
} elsif ($cmd eq 'cleancache') {
  $farm->cleanSSHKeyCache;
} else {
  print "invalid command\n";
}
$farm->waitOnActions;
